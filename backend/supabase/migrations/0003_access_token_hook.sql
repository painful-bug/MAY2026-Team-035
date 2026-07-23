-- 0003_access_token_hook.sql
-- Custom Access Token Hook: injects the user's role into every issued JWT as a
-- top-level `user_role` claim. Both the FastAPI guards (app/core/security.py)
-- and the RLS policies (0002) read this claim, so the profile's role is the one
-- authoritative source that flows everywhere.
--
-- AFTER running this migration you MUST register the hook in the dashboard:
--   Authentication -> Hooks -> Customize Access Token (JWT) Claims
--   -> select `public.custom_access_token_hook`.
-- (Or set auth.hook.custom_access_token.* in config.toml for local dev.)

create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
as $$
declare
  claims    jsonb;
  user_role public.user_role;
begin
  select role into user_role
  from public.profiles
  where id = (event ->> 'user_id')::uuid;

  claims := event -> 'claims';

  if user_role is not null then
    claims := jsonb_set(claims, '{user_role}', to_jsonb(user_role::text));
  else
    -- No profile yet: default to RESIDENT so a valid role claim always exists.
    claims := jsonb_set(claims, '{user_role}', to_jsonb('RESIDENT'::text));
  end if;

  return jsonb_set(event, '{claims}', claims);
end;
$$;

-- The Auth admin role must be able to read profiles and execute the hook.
grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin;
grant select on table public.profiles to supabase_auth_admin;

-- Keep the hook private to the platform.
revoke execute on function public.custom_access_token_hook(jsonb) from authenticated, anon, public;
