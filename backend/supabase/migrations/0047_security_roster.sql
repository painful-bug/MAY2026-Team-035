-- 0047_security_roster.sql
--
-- One read function, and it exists because of a hole task #93's frontend build
-- found between two permission models. Creating a shift
-- (`schedule_security_shift`, 0040) needs a `staff_assignments` id, and the
-- person who creates shifts is usually a security *manager* — a `security`
-- membership whose roster rank is `manager` or `supervisor` (D3 made rank and
-- role separate axes). But every roster read this schema has lives under the
-- department-hiring surface, whose router guard is the *membership* role
-- (`admin` or `manager`) — so the one person the shift form is for is the one
-- person who cannot fetch the list of guards to put in it.
--
-- `security_roster` closes that hole with the same predicate the shift writes
-- already trust: `gate_admin_community_for` (0040 §7) raises `HB403` for
-- anyone who may not run the roster, and returns the community whose staff to
-- list for everyone who may. Deliberately narrower than what
-- `schedule_security_shift` accepts: the RPC will roster any active staff row
-- in the community (a typed-in name with no membership is a valid guard), but
-- the *picker* lists only staff of departments whose `kind = 'security'`
-- (0035) — a shift form that offers the plumbing roster is offering a mistake.
--
-- A function rather than a view, because the answer depends on who is asking:
-- RLS on `staff_assignments` was written for the hiring surface and does not
-- know the gate-admin predicate, and a view cannot raise HB403. No table, no
-- view, no column — the ERD and the class diagram are untouched by this file.

create or replace function public.security_roster(p_membership_id uuid)
returns table (
  staff_assignment_id uuid,
  display_name        text,
  phone_e164          varchar,
  job_title           text,
  rank                text,
  shift               text
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_admin_community_for(p_membership_id);
begin
  return query
    select
      s.id,
      s.display_name,
      s.phone_e164,
      s.job_title,
      s.rank,
      s.shift
    from public.staff_assignments s
    join public.departments d on d.id = s.department_id
   where s.community_id = v_community
     and s.status = 'active'
     and d.kind = 'security'
   order by lower(s.display_name);
end;
$$;

grant execute on function public.security_roster(uuid) to authenticated;

comment on function public.security_roster(uuid) is
  'Active security-department staff of the caller''s community, for the '
  'shift form''s guard picker. Gate managers only (gate_admin_community_for, '
  'HB403 otherwise). Narrower than what schedule_security_shift accepts, on '
  'purpose.';
