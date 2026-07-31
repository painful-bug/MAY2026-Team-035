-- The hosted project predates authenticated self-service join requests. Keep
-- historic rows intact, but bind every new request to the Supabase profile
-- that submitted it so ownership, pending-request uniqueness, and admin
-- approval remain tenant-safe.
alter table public.access_requests
  add column if not exists applicant_profile_id uuid
  references public.profiles(id) on delete cascade;

alter table public.access_requests
  drop constraint if exists access_requests_applicant_profile_required;

-- NOT VALID preserves legacy rows that cannot be safely attributed after the
-- fact, while PostgreSQL still enforces the constraint for every new write.
alter table public.access_requests
  add constraint access_requests_applicant_profile_required
  check (applicant_profile_id is not null) not valid;

create unique index if not exists access_requests_one_pending_per_profile_community
  on public.access_requests(community_id, applicant_profile_id)
  where status = 'pending';

notify pgrst, 'reload schema';
