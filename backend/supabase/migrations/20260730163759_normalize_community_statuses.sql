-- Legacy tooling stored title-cased values such as "Active" in this text
-- column.  Application and RPC authorization filters deliberately use a
-- canonical lower-case value, so normalize the existing rows before adding
-- the invariant for all future writes.
update public.communities
set status = lower(btrim(status))
where status is distinct from lower(btrim(status));

alter table public.communities
  drop constraint if exists communities_status_canonical;

alter table public.communities
  add constraint communities_status_canonical
  check (status = lower(btrim(status)) and length(btrim(status)) > 0);
