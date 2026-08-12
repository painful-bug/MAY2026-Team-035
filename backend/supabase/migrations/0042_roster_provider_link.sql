-- A roster row says which service provider it is, if it is one.
--
-- docs/plans/SERVICE_OPERATIONS_PROGRESS.md 4.26.
--
-- WHAT WAS MISSING, AND HOW IT STAYED MISSING FOR FIVE MIGRATIONS
--
-- `0035` added `staff_assignments.service_provider_id`, which is the link
-- between a hired service person and their place on a department's roster. The
-- write path fills it: `decide_service_application` inserts the staff row with
-- the provider id and the membership id in the same transaction.
--
-- Nothing reads it. `department_staff_overview` is from `0019`, predates the
-- column by sixteen migrations, and projects fourteen fields that do not include
-- it. So every read the admin dashboard has -- `GET /departments`,
-- `GET /departments/{id}/staff` -- returns a hired plumber and a name somebody
-- typed into a form as **the same shape**, with no way to tell them apart.
--
-- That is only an abstraction leak until a screen needs to act on the
-- difference, and then it is a wall. The hiring screen's roster tab offers two
-- verbs on one row:
--
--   remove    POST /departments/{id}/members/{staffId}/remove   -> staff_assignments.id
--   blacklist POST /departments/{id}/blacklist                  -> service_providers.id
--
-- One read carries the first id and no read carries the second, so the two
-- buttons could not sit on the same card. The alternatives were both worse: a
-- second request per row to work out who a roster entry is, or a roster
-- assembled out of `service_applications` rows filtered to `accepted`, which
-- would silently omit every typed-in name and call the result a roster.
--
-- This is the third time in this build that writing the consumer proved a read
-- stopped one field short -- see 4.22 and 4.26 in the progress journal. The
-- pattern is worth naming: a field that only the *write* path uses looks
-- complete in every test, because the test asserts the write.
--
-- ALSO: the view had a grant that belonged to a different view.
--
-- `0019` ends with `grant select on public.department_overview to authenticated`
-- inside this view's own section, immediately before the same grant for this
-- one. Harmless -- the duplicate is idempotent and both views are granted -- but
-- the recreation below drops the view, so its grant has to be reissued here or
-- the endpoint 403s. Named because "recreating a view silently drops its
-- grants" is the kind of thing that gets rediscovered at three in the morning.

drop view if exists public.department_staff_overview;
create view public.department_staff_overview
with (security_invoker = true) as
select
  s.id,
  s.community_id,
  s.department_id,
  s.membership_id,
  -- The new column, and the only change to the projection.
  s.service_provider_id,
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
  'Staff assignments with the number of open complaints each member holds in that department, and the service provider behind the row when there is one. A null service_provider_id means a name on a roster with no account -- which 0019 A7 made the ordinary case and 0035 stopped making the only one.';

grant select on public.department_staff_overview to authenticated;
