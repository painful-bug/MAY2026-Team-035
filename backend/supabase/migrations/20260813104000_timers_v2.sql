-- Complaint Engine v2: manual window and auto-close timers.

alter table public.dispatch_tasks add column if not exists complaint_id uuid references public.complaints(id) on delete cascade;
alter table public.dispatch_tasks drop constraint if exists dispatch_tasks_kind_check;
alter table public.dispatch_tasks add constraint dispatch_tasks_kind_check check (kind in (
  'ping', 'auto_assign', 'resident_timeout', 'failed_visit_escalation', 'departure_removal',
  'manual_window', 'auto_close_warning', 'auto_close'));
alter table public.dispatch_tasks drop constraint if exists dispatch_tasks_one_subject;
alter table public.dispatch_tasks add constraint dispatch_tasks_one_subject
  check (num_nonnulls(work_order_id, departure_id, complaint_id) = 1);
create unique index if not exists dispatch_tasks_one_open_per_complaint_kind
  on public.dispatch_tasks (complaint_id, kind) where completed_at is null and complaint_id is not null;

create or replace function public.enqueue_complaint_dispatch_task(p_complaint_id uuid, p_kind text, p_due_at timestamptz)
returns uuid language plpgsql security definer set search_path = public
as $$
declare v_id uuid;
begin
  insert into public.dispatch_tasks (complaint_id, kind, due_at) values (p_complaint_id, p_kind, p_due_at)
  on conflict (complaint_id, kind) where completed_at is null and complaint_id is not null
  do update set due_at = excluded.due_at, claimed_at = null, attempts = 0, last_error = null
  returning id into v_id;
  return v_id;
end;
$$;

-- CHANGED: accepted resident slots wait for a human offer, even when high priority.
create or replace function public.sync_dispatch_tasks()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  if new.status = 'awaiting_resident' then
    if tg_op = 'INSERT' or old.status is distinct from new.status or old.resident_deadline_at is distinct from new.resident_deadline_at then
      perform public.enqueue_dispatch_task(new.id, 'resident_timeout', coalesce(new.resident_deadline_at, now() + interval '24 hours'));
    end if;
  elsif new.status = 'offered' then
    if tg_op = 'INSERT' or old.status is distinct from new.status or old.scheduled_start_at is distinct from new.scheduled_start_at then
      perform public.close_dispatch_tasks(new.id, array['resident_timeout']);
      perform public.enqueue_dispatch_task(new.id, 'manual_window', now() + case when new.priority = 'high' then interval '2 hours' else interval '24 hours' end, case when new.priority = 'high' then 2 else 0 end);
    end if;
  elsif new.status = 'failed' then
    if tg_op = 'INSERT' or old.status is distinct from new.status then
      perform public.close_dispatch_tasks(new.id, null);
      perform public.enqueue_dispatch_task(new.id, 'failed_visit_escalation', now() + interval '2 hours');
    end if;
  elsif tg_op = 'INSERT' or old.status is distinct from new.status then
    perform public.close_dispatch_tasks(new.id, null);
  end if;
  return new;
end;
$$;

create or replace function public.dispatch_manual_window(p_work_order_id uuid)
returns boolean language plpgsql security definer set search_path = public
as $$
declare v_order public.work_orders%rowtype;
begin
  select * into v_order from public.work_orders where id = p_work_order_id for update;
  if not found or v_order.status <> 'offered' then return false; end if;
  if exists (select 1 from public.work_order_assignments a where a.work_order_id = p_work_order_id and a.status in ('offered', 'accepted')) then return false; end if;
  perform public.dispatch_ping_candidates(p_work_order_id);
  perform public.notify_complaint_staff(v_order.complaint_id, 'job.fallback_started', jsonb_build_object('title', 'The system is finding someone', 'complaint_id', v_order.complaint_id));
  return true;
end;
$$;

create or replace function public.on_complaint_resolved()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  if new.status = 'resolved' and old.status is distinct from 'resolved' then
    perform public.enqueue_complaint_dispatch_task(new.id, 'auto_close_warning', now() + interval '48 hours');
    perform public.enqueue_complaint_dispatch_task(new.id, 'auto_close', now() + interval '72 hours');
    insert into public.complaint_events (complaint_id, event_type, payload) values (new.id, 'status_changed', jsonb_build_object('to', 'resolved'));
    if new.raised_by_membership_id is not null then perform public.notify_member(new.raised_by_membership_id, 'complaint.resolved', jsonb_build_object('title', 'Your complaint was resolved', 'url', '/resident/complaints?complaint=' || new.id::text, 'complaint_id', new.id)); end if;
  end if;
  return new;
end;
$$;
drop trigger if exists complaints_on_resolved on public.complaints;
create trigger complaints_on_resolved after update of status on public.complaints
for each row execute function public.on_complaint_resolved();

create or replace function public.dispatch_auto_close(p_complaint_id uuid, p_warn boolean)
returns boolean language plpgsql security definer set search_path = public
as $$
declare v public.complaints%rowtype;
begin
  select * into v from public.complaints where id = p_complaint_id for update;
  if not found or v.status <> 'resolved' then return false; end if;
  if p_warn then
    insert into public.complaint_events (complaint_id, event_type, payload) values (v.id, 'auto_close_warning', '{}'::jsonb);
    if v.raised_by_membership_id is not null then perform public.notify_member(v.raised_by_membership_id, 'complaint.auto_close_warning', jsonb_build_object('title', 'Confirm or reopen — this closes itself in 24 hours.', 'url', '/resident/complaints?complaint=' || v.id::text, 'complaint_id', v.id)); end if;
  else
    update public.complaints set status = 'closed', updated_at = now() where id = v.id;
    insert into public.complaint_events (complaint_id, event_type, payload) values (v.id, 'auto_closed', '{}'::jsonb);
    if v.raised_by_membership_id is not null then perform public.notify_member(v.raised_by_membership_id, 'complaint.auto_closed', jsonb_build_object('title', 'Complaint closed automatically', 'url', '/resident/complaints?complaint=' || v.id::text, 'complaint_id', v.id)); end if;
  end if;
  return true;
end;
$$;

create or replace function public.fire_dispatch_task(p_task_id uuid)
returns text language plpgsql security definer set search_path = public
as $$
declare v_task public.dispatch_tasks%rowtype; v_result text; v_id uuid;
begin
  select * into v_task from public.dispatch_tasks where id = p_task_id for update;
  if not found then return 'missing'; end if;
  if v_task.completed_at is not null then return 'already_done'; end if;
  case v_task.kind
    when 'ping' then v_result := 'offered:' || public.dispatch_ping_candidates(v_task.work_order_id)::text;
    when 'auto_assign' then v_id := public.dispatch_auto_assign(v_task.work_order_id); v_result := coalesce('assigned:' || v_id::text, 'no_candidate');
    when 'resident_timeout' then v_result := case when public.dispatch_resident_timeout(v_task.work_order_id) then 'proceeded' else 'skipped' end;
    when 'failed_visit_escalation' then v_result := case when public.dispatch_failed_visit_escalation(v_task.work_order_id) then 'escalated' else 'skipped' end;
    when 'departure_removal' then v_result := case when public.dispatch_departure_removal(v_task.departure_id) then 'removed' else 'skipped' end;
    when 'manual_window' then v_result := case when public.dispatch_manual_window(v_task.work_order_id) then 'fallback_started' else 'skipped' end;
    when 'auto_close_warning' then v_result := case when public.dispatch_auto_close(v_task.complaint_id, true) then 'warned' else 'skipped' end;
    when 'auto_close' then v_result := case when public.dispatch_auto_close(v_task.complaint_id, false) then 'closed' else 'skipped' end;
    else update public.dispatch_tasks set last_error = 'No handler for kind: ' || v_task.kind, completed_at = now() where id = p_task_id; return 'unsupported';
  end case;
  update public.dispatch_tasks set completed_at = now(), last_error = null where id = p_task_id;
  return v_result;
end;
$$;

do $$ begin
  if not exists (select 1 from pg_constraint where conrelid='public.dispatch_tasks'::regclass and conname='dispatch_tasks_kind_check') then raise exception 'dispatch kind check missing'; end if;
end $$;
