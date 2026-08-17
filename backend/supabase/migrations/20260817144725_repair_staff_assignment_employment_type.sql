-- The hosted legacy schema allowed only ``internal`` and ``vendor`` while the
-- atomic service-hiring RPC has always written ``staff``. Keep both legacy
-- values and admit the value emitted by the live RPC.
alter table public.staff_assignments
  drop constraint if exists staff_assignments_employment_type_check;

alter table public.staff_assignments
  add constraint staff_assignments_employment_type_check
  check (employment_type in ('internal', 'vendor', 'staff'));
