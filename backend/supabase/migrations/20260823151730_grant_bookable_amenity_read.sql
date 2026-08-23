-- `bookable_amenity` is a security-invoker view, so the authenticated backend
-- client needs this underlying read permission for resident catalogue requests.
grant select on table public.amenities to authenticated;
