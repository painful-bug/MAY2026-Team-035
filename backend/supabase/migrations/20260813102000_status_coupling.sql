-- Complaint Engine v2: work-order status projection and safety guards.

create or replace function public.project_complaint_from_jobs()
returns trigger language plpgsql security definer set search_path = public
as $$
declare v_complaint_id uuid; v_live integer;
begin
  v_complaint_id := coalesce(new.complaint_id, (select w.complaint_id from public.work_orders w where w.id = new.work_order_id));
  if tg_table_name = 'work_order_assignments' and tg_op = 'INSERT' and new.status = 'offered' then
    update public.complaints set status = 'acknowledged', updated_at = now() where id = v_complaint_id and status = 'open';
  elsif tg_table_name = 'work_orders' and new.status = 'in_progress' then
    update public.complaints set status = 'in_progress', updated_at = now() where id = v_complaint_id and status in ('open', 'acknowledged');
  elsif tg_table_name = 'work_orders' and new.status = 'completed' then
    select count(*) into v_live from public.work_orders w where w.complaint_id = v_complaint_id and w.id <> new.id and w.status in ('draft', 'awaiting_resident', 'offered', 'scheduled', 'in_progress');
    if v_live = 0 then
      update public.complaints set status = 'resolved', updated_at = now() where id = v_complaint_id and status in ('open', 'acknowledged', 'in_progress');
    end if;
  end if;
  return new;
end;
$$;
drop trigger if exists work_orders_project_complaint on public.work_orders;
create trigger work_orders_project_complaint after update of status on public.work_orders
for each row when (new.status in ('in_progress', 'completed')) execute function public.project_complaint_from_jobs();
drop trigger if exists work_order_assignments_project_complaint on public.work_order_assignments;
create trigger work_order_assignments_project_complaint after insert on public.work_order_assignments
for each row when (new.status = 'offered') execute function public.project_complaint_from_jobs();

-- Shared database guard: covers create_work_order and any future direct writer.
create or replace function public.guard_live_work_order_complaint()
returns trigger language plpgsql security definer set search_path = public
as $$
declare v_status text;
begin
  select status::text into v_status from public.complaints where id = new.complaint_id;
  if v_status in ('resolved', 'closed', 'cancelled') then
    raise exception 'Reopen the complaint to raise more work.' using errcode = 'HB409';
  end if;
  return new;
end;
$$;
drop trigger if exists work_orders_terminal_complaint_guard on public.work_orders;
create trigger work_orders_terminal_complaint_guard before insert on public.work_orders
for each row execute function public.guard_live_work_order_complaint();

-- Department movement is protected at the table boundary so both allocation
-- and accepted transfer requests cannot strand a live job.
create or replace function public.guard_complaint_department_transfer()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  if new.department_id is distinct from old.department_id and exists (
    select 1 from public.work_orders w where w.complaint_id = new.id
      and w.status in ('draft', 'awaiting_resident', 'offered', 'scheduled', 'in_progress')
  ) then
    raise exception 'Cancel or finish the open job first.' using errcode = 'HB409';
  end if;
  return new;
end;
$$;
drop trigger if exists complaints_department_live_work_guard on public.complaints;
create trigger complaints_department_live_work_guard before update of department_id on public.complaints
for each row execute function public.guard_complaint_department_transfer();

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'work_orders_project_complaint') then raise exception 'status projection trigger missing'; end if;
end $$;
