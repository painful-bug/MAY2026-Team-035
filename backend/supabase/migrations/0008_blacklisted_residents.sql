-- Compatibility migration for existing projects.  0001_baseline.sql remains
-- the full fresh-project schema; apply this to a Supabase development branch.
-- The legacy project predates the fuzzy-search extension used by the indexed
-- type-ahead query, so provision it before compiling the replacement RPC.
create extension if not exists pg_trgm with schema extensions;

create table if not exists public.blacklisted_residents (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  blacklisted_by_membership_id uuid not null references public.community_memberships(id) on delete restrict,
  reason text not null check (length(btrim(reason)) between 3 and 500),
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  revoked_by_membership_id uuid references public.community_memberships(id) on delete set null
);
create unique index if not exists blacklisted_residents_one_active_per_community_profile
  on public.blacklisted_residents(community_id, profile_id) where revoked_at is null;
alter table public.blacklisted_residents enable row level security;
create index if not exists communities_active_name_trgm
  on public.communities using gin (lower(name) extensions.gin_trgm_ops) where status='active';

create or replace function public.search_joinable_communities(p_query text, p_limit integer default 10, p_profile_id uuid default null)
returns table(id uuid,name text,community_type text,city text,state text)
language sql stable security definer set search_path=public, extensions as $$
  select c.id,c.name,c.community_type,c.city,c.state from public.communities c
  where c.status='active' and length(btrim(p_query)) between 2 and 100
    and lower(c.name) % lower(btrim(p_query))
    and not exists(select 1 from public.blacklisted_residents b where b.community_id=c.id and b.profile_id=p_profile_id and b.revoked_at is null)
  order by case when lower(c.name) like lower(btrim(p_query)) || '%' then 0 else 1 end, similarity(lower(c.name),lower(btrim(p_query))) desc,c.name,c.id
  limit least(greatest(coalesce(p_limit,10),1),20)
$$;

create or replace function public.blacklist_access_request(p_request_id uuid,p_reviewer_profile_id uuid,p_reason text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare request_row public.access_requests%rowtype; reviewer uuid;
begin
  select * into request_row from public.access_requests where id=p_request_id for update;
  if request_row.id is null or request_row.status <> 'pending' then raise exception 'Access request is no longer pending'; end if;
  select id into reviewer from public.community_memberships where profile_id=p_reviewer_profile_id and community_id=request_row.community_id and role='admin' and status='active' and ended_at is null limit 1;
  if reviewer is null then raise exception 'Administrator access is required'; end if;
  insert into public.blacklisted_residents(community_id,profile_id,blacklisted_by_membership_id,reason)
  values(request_row.community_id,request_row.applicant_profile_id,reviewer,left(btrim(p_reason),500))
  on conflict (community_id,profile_id) where revoked_at is null do update set reason=excluded.reason,blacklisted_by_membership_id=excluded.blacklisted_by_membership_id;
  update public.access_requests set status='rejected',reviewed_by_membership_id=reviewer,reviewed_at=now(),rejection_reason=left(btrim(p_reason),500),updated_at=now() where id=request_row.id;
  return jsonb_build_object('request_id',request_row.id,'status','rejected','blacklisted',true);
end $$;

revoke all on function public.search_joinable_communities(text,integer,uuid) from public, anon, authenticated;
revoke all on function public.blacklist_access_request(uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.search_joinable_communities(text,integer,uuid) to service_role;
grant execute on function public.blacklist_access_request(uuid,uuid,text) to service_role;

notify pgrst, 'reload schema';
