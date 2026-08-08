-- The join form and API deliberately accept an omitted phone number.  Older
-- hosted projects predate that contract and still require this column.
alter table public.access_requests
  alter column applicant_phone_e164 drop not null;

notify pgrst, 'reload schema';
