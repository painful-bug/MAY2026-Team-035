-- Complaint Engine v2: resident cancellation and re-evaluation pool.

alter table public.complaints add column if not exists returned_to_pool_at timestamptz;

-- CHANGED: creating a replacement job means the complaint has left the pool.
create or replace function public.clear_complaint_pool_flag()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  update public.complaints set returned_to_pool_at = null
   where id = new.complaint_id and returned_to_pool_at is not null;
  return new;
end;
$$;
drop trigger if exists work_orders_clear_complaint_pool_flag on public.work_orders;
create trigger work_orders_clear_complaint_pool_flag after insert on public.work_orders
for each row execute function public.clear_complaint_pool_flag();

create or replace function public.resident_cancel_work(
  p_complaint_id uuid, p_mode text, p_reason text default null
) returns void language plpgsql security definer set search_path = public
as $$
declare v_complaint public.complaints%rowtype; v_order public.work_orders%rowtype; v_reason text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  if p_mode not in ('cancel', 'repool') then raise exception 'Unknown cancellation mode: %', p_mode using errcode = '22P02'; end if;
  select * into v_complaint from public.complaints where id = p_complaint_id for update;
  if not found or not public.is_own_membership(v_complaint.raised_by_membership_id) then raise exception 'No such complaint.' using errcode = 'HB404'; end if;
  select w.* into v_order from public.work_orders w where w.complaint_id = p_complaint_id and w.status in ('offered', 'scheduled') order by w.created_at desc limit 1 for update;
  if not found then raise exception 'There is nothing to cancel right now.' using errcode = 'HB409'; end if;
  if exists (select 1 from public.work_orders w where w.complaint_id = p_complaint_id and w.status = 'in_progress') then raise exception 'Work has begun — contact the office to cancel.' using errcode = 'HB409'; end if;
  update public.work_order_assignments set status = 'withdrawn', responded_at = now(), ended_at = now() where work_order_id = v_order.id and status in ('offered', 'accepted');
  update public.work_orders set status = 'cancelled', cancelled_by = 'resident', updated_at = now() where id = v_order.id;
  if p_mode = 'cancel' then
    update public.complaints set status = 'cancelled', updated_at = now() where id = p_complaint_id;
    insert into public.complaint_events (complaint_id, actor_membership_id, event_type, payload) values (p_complaint_id, v_complaint.raised_by_membership_id, 'status_changed', jsonb_build_object('to', 'cancelled', 'reason', v_reason));
  else
    update public.complaints set status = 'open', returned_to_pool_at = now(), updated_at = now() where id = p_complaint_id;
    insert into public.complaint_events (complaint_id, actor_membership_id, event_type, payload) values (p_complaint_id, v_complaint.raised_by_membership_id, 'returned_to_pool', jsonb_build_object('reason', v_reason));
  end if;
  perform public.notify_complaint_staff(p_complaint_id, 'complaint.job_cancelled_by_resident', jsonb_build_object('title', 'Resident cancelled scheduled work', 'complaint_id', p_complaint_id));
end;
$$;
grant execute on function public.resident_cancel_work(uuid, text, text) to authenticated;

drop function if exists public.department_complaints(uuid, text);
create function public.department_complaints(p_department_id uuid, p_status text default null)
returns table (
  id uuid, title text, description text, category text, status text, priority text,
  location text, created_at timestamptz, due_at timestamptz, resolved_at timestamptz,
  raised_by text, unit_code text, open_request_id uuid, returned_to_pool_at timestamptz,
  reopened_count integer
) language plpgsql stable security definer set search_path = public
as $$
begin
  if not public.can_supervise_department(p_department_id) then raise exception 'You do not work on this department''s complaints.' using errcode = 'HB403'; end if;
  return query select c.id, c.title, c.description, c.category, c.status::text, c.priority, c.location,
    c.created_at, c.due_at, c.resolved_at, coalesce(p.full_name, 'A resident'), u.unit_code,
    r.id, c.returned_to_pool_at, c.reopened_count
  from public.complaints c
  left join public.community_memberships m on m.id = c.raised_by_membership_id
  left join public.profiles p on p.id = m.profile_id
  left join public.unit_residencies ur on ur.membership_id = m.id and ur.ended_at is null
  left join public.units u on u.id = ur.unit_id
  left join public.complaint_department_requests r on r.complaint_id = c.id and r.status = 'pending'
  where c.department_id = p_department_id and (p_status is null or c.status::text = p_status)
  order by c.created_at desc;
end;
$$;
grant execute on function public.department_complaints(uuid, text) to authenticated;

do $$ begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='complaints' and column_name='returned_to_pool_at') then raise exception 'returned_to_pool_at missing'; end if;
end $$;
