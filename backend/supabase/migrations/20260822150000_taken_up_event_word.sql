-- 20260822150000_taken_up_event_word.sql
--
-- `take_up_complaint` (20260822120000) writes a `complaint_events` row with
-- `event_type = 'taken_up'` -- a word `complaint_events_type_check`
-- (20260813105000 77) does not allow. The very first live Take-up press
-- answered 23514:
--
--   new row for relation "complaint_events" violates check constraint
--   "complaint_events_type_check"
--
-- found live 2026-08-22 on the supervisor dashboard. 20260822120000 155
-- reasoned from `0001_baseline.sql` 70 ("event_type is text with no CHECK")
-- and missed that 20260813105000 had bolted the constraint on later. The
-- vocabulary is the thing that changed, so the constraint is what moves:
-- same drop-and-recreate shape as the file that created it, with `taken_up`
-- as the one new word.
--
-- Hand-applied by the owner in the Supabase SQL editor, like every file in
-- this directory. Idempotent: re-running drops and recreates the same
-- constraint.

-- Nothing already stored may be outside the new list, or the ADD below would
-- fail halfway with the constraint dropped. Checked first, so failure here
-- leaves the old constraint standing untouched.
do $$
declare v_bad text;
begin
  select event_type into v_bad from public.complaint_events where event_type not in (
    'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
    'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
    'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
    'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up') limit 1;
  if v_bad is not null then raise exception 'Unknown existing complaint event type: %', v_bad; end if;
end $$;

alter table public.complaint_events drop constraint if exists complaint_events_type_check;
alter table public.complaint_events add constraint complaint_events_type_check check (event_type in (
  'raised','status_changed','assigned','progress_changed','due_date_changed','note_added','comment_added','reopened','resolution_confirmed',
  'job_created','job_scheduled','job_declined','job_assigned','job_cancelled','job_started','job_completed','job_failed',
  'department_assigned','department_change_requested','department_change_accepted','department_change_rejected',
  'job_force_assigned','returned_to_pool','auto_close_warning','auto_closed','taken_up'));

-- The constraint is back, and it knows the new word.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.complaint_events'::regclass
      and conname  = 'complaint_events_type_check'
      and pg_get_constraintdef(oid) like '%taken_up%'
  ) then raise exception 'complaint event type check missing or does not allow taken_up'; end if;
end $$;
