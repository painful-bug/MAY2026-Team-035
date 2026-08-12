-- Complaint Engine v2: chat auto-open, event vocabulary, and staff detail.

-- One accept-side writer covers manual consent, force assignment, and auto assignment.
create or replace function public.open_accepted_work_order_thread()
returns trigger language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype; v_worker uuid; v_resident uuid; v_a uuid; v_b uuid; v_thread uuid;
begin
  if new.status <> 'accepted' then return new; end if;
  select * into v_order from public.work_orders where id = new.work_order_id;
  select m.profile_id into v_worker from public.staff_assignments sa join public.community_memberships m on m.id = sa.membership_id where sa.id = new.staff_assignment_id;
  select m.profile_id into v_resident from public.complaints c join public.community_memberships m on m.id = c.raised_by_membership_id where c.id = v_order.complaint_id;
  if v_worker is null or v_resident is null or v_worker = v_resident then return new; end if;
  v_a := least(v_worker, v_resident); v_b := greatest(v_worker, v_resident);
  select id into v_thread from public.dm_threads where kind = 'work_order' and work_order_id = v_order.id and locked_at is null limit 1;
  if v_thread is null then
    insert into public.dm_threads (community_id, kind, work_order_id, participant_a_profile_id, participant_b_profile_id, participant_a_name, participant_b_name)
    select v_order.community_id, 'work_order', v_order.id, v_a, v_b,
      coalesce((select full_name from public.profiles where id = v_a), 'Someone'),
      coalesce((select full_name from public.profiles where id = v_b), 'Someone')
    returning id into v_thread;
    insert into public.dm_messages (thread_id, author_profile_id, body) values (v_thread, null, 'You''re connected about this job — agree the details here.');
    update public.dm_threads set last_message_at = now() where id = v_thread;
  end if;
  return new;
end;
$$;
drop trigger if exists work_order_assignments_open_chat on public.work_order_assignments;
create trigger work_order_assignments_open_chat after insert or update of status on public.work_order_assignments
for each row when (new.status = 'accepted') execute function public.open_accepted_work_order_thread();

-- CHANGED: worker cards need the force flag written by the new assignment path.
drop view if exists public.my_worker_job;
create view public.my_worker_job with (security_invoker = true) as
select a.id as assignment_id, a.work_order_id, a.staff_assignment_id,
  a.status as assignment_status, a.offered_at, a.responded_at, a.decline_reason,
  a.is_auto_assigned, a.is_forced,
  coalesce(a.scheduled_start_at, w.scheduled_start_at) as scheduled_start_at,
  coalesce(a.scheduled_end_at, w.scheduled_end_at) as scheduled_end_at,
  w.status as work_order_status, w.priority, w.subject_kind, w.location_text,
  w.failed_attempt_count, w.cancelled_reason, w.community_id, cm.name as community_name,
  w.department_id, d.name as department_name, d.kind as department_kind,
  w.complaint_id, c.title as complaint_title, c.description as complaint_description,
  c.category as complaint_category, sk.name as skill_name,
  res.full_name as resident_name, res.phone_e164 as resident_phone_e164,
  res.unit_code as resident_unit_code
from public.work_order_assignments a
join public.work_orders w on w.id = a.work_order_id
left join public.communities cm on cm.id = w.community_id
left join public.departments d on d.id = w.department_id
left join public.complaints c on c.id = w.complaint_id
left join public.skills sk on sk.id = w.skill_id
left join lateral (
  select p.full_name, p.phone_e164, u.unit_code
  from public.community_memberships m join public.profiles p on p.id = m.profile_id
  left join lateral (
    select un.unit_code from public.unit_residencies ur join public.units un on un.id = ur.unit_id
    where ur.membership_id = m.id and ur.ended_at is null
    order by ur.is_primary_contact desc, ur.started_at limit 1
  ) u on true
  where m.id = c.raised_by_membership_id and w.subject_kind = 'resident'
) res on true
where public.is_own_staff_assignment(a.staff_assignment_id);
grant select on public.my_worker_job to authenticated;

do $$
declare v_bad text;
begin
  select event_type into v_bad from public.complaint_events where event_type not in (
    'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
    'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
    'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
    'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed') limit 1;
  if v_bad is not null then raise exception 'Unknown existing complaint event type: %', v_bad; end if;
end $$;
alter table public.complaint_events drop constraint if exists complaint_events_type_check;
alter table public.complaint_events add constraint complaint_events_type_check check (event_type in (
  'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
  'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
  'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
  'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed'));

create or replace function public.staff_complaint_detail(p_complaint_id uuid)
returns jsonb language plpgsql stable security definer set search_path = public
as $$
declare v public.complaints%rowtype;
begin
  select * into v from public.complaints where id = p_complaint_id;
  if not found then raise exception 'No such complaint.' using errcode = 'HB404'; end if;
  if not (public.is_community_admin(v.community_id) or (v.department_id is not null and public.can_supervise_department(v.department_id))) then raise exception 'No such complaint.' using errcode = 'HB404'; end if;
  return jsonb_build_object('complaint', to_jsonb(v), 'events', (select coalesce(jsonb_agg(to_jsonb(e) order by e.created_at), '[]'::jsonb) from public.complaint_events e where e.complaint_id = v.id));
end;
$$;
grant execute on function public.staff_complaint_detail(uuid) to authenticated;

do $$ begin
  if not exists (select 1 from pg_constraint where conrelid='public.complaint_events'::regclass and conname='complaint_events_type_check') then raise exception 'complaint event type check missing'; end if;
end $$;
