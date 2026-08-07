-- The resident's half of the amenity catalogue, as a view.
--
-- `GET /amenities/available` shipped reading `public.amenities` directly. That
-- was the one read in either backend that did not go through a view, and it was
-- recorded as a divergence rather than quietly counted as compliance -- see
-- docs/design/RESIDENT_BACKEND_DESIGN.md 12, "The one item that is not a clean
-- tick". This file closes it.
--
-- WHY NOT JUST READ `amenity_overview`
--
-- Because it is the *admin* card's projection. Two lateral aggregates hang off
-- every row -- one counting bookings by status, one summing charges against
-- payments to produce `outstanding_dues` -- and a resident is shown neither.
-- The cost is the smaller half of the argument. The larger half is that sharing
-- it would leave the resident response one column away from an admin field: the
-- next column added to that view for the admin card would be in scope for the
-- resident payload the moment it was added, by someone who had no reason to
-- think about residents at all. That is finding 3.1 exactly -- an amenity read
-- shaped for one role and then handed to another.
--
-- So: two views over one table, each owned by the surface that reads it.
-- Nothing here is computed, joined or aggregated; the whole content of this view
-- is *which rows and which columns a resident may see*, which is precisely what
-- a view is for.
--
-- WHAT "BOOKABLE" MEANS, AND WHAT IT DOES NOT
--
-- Bookable in principle: the amenity exists, is active, and is not under a
-- temporary closure. It does **not** mean free at a particular time. Whether a
-- slot is free is decided on write by `amenity_occurrence_guard` under an
-- advisory lock, never by a read -- a read that answered "free" would be
-- answering about a moment already past by the time the resident submitted.
--
-- ROW SECURITY
--
-- `security_invoker = true`, as every other view here. It changes nothing today
-- and that is worth stating plainly rather than leaving someone to discover it:
-- `public.amenities` carries no RLS policy of its own, so the caller's rights
-- and the definer's amount to the same thing, and the `community_id` filter the
-- API applies from the resolved membership is the entire tenancy boundary. The
-- flag is set so that the day a policy is added to `amenities` -- by the
-- workstream that owns 0023, whose table it is -- this view inherits it instead
-- of silently bypassing it.
--
-- No index is added for this read. A community's catalogue is tens of rows, and
-- `amenities` belongs to the admin workstream; a scan that costs nothing is not
-- worth reaching into another workstream's table for.

-- ---------------------------------------------------------------------------
-- 1. The view
-- ---------------------------------------------------------------------------

drop view if exists public.bookable_amenity;
create view public.bookable_amenity
with (security_invoker = true) as
select
  a.id,
  -- Not shown to anyone. It is here because it is the filter the API applies
  -- from the resolved membership, and a tenancy boundary the view cannot
  -- express is one the caller must be able to.
  a.community_id,
  a.name,
  a.description,
  a.category,
  a.location,
  a.image_url,
  a.capacity,
  a.booking_mode,
  a.approval_required,
  a.opening_time,
  a.closing_time,
  a.slot_duration_minutes,
  a.minimum_booking_duration_minutes,
  a.maximum_booking_duration_minutes,
  a.advance_booking_window_days,
  a.max_active_bookings_per_resident,
  a.closed_days,
  a.allow_private_booking,
  a.allow_guest_booking,
  a.allow_recurring_booking,
  a.allow_same_day_booking,
  a.booking_fee,
  a.security_deposit,
  a.currency_code,
  a.refund_policy,
  -- Selected even though the filter below has already excluded every row where
  -- it is truthy. The service applies the same test again in Python, and this
  -- column is what lets it: see the note under section 2.
  a.temporary_closure
from public.amenities a
where a.status = 'active'
  and a.is_active
  -- `status` and `is_active` are both tested even though `sync_amenity_status`
  -- in 0023 keeps them in agreement. The trigger is what makes them agree; this
  -- is what keeps the view correct if the trigger is ever dropped.
  and (
    a.temporary_closure is null
    -- Every jsonb value Python's `bool()` reads as false, spelled out. The
    -- column is unconstrained, so "is it null" and "is it empty" are different
    -- questions and the settings form clears a closure by writing `{}`. Written
    -- as an exact transcription of the Python test rather than an approximation
    -- of it, because two readers disagreeing about whether the pool is shut is
    -- worse than either answer on its own.
    or a.temporary_closure in (
      'null'::jsonb, '{}'::jsonb, '[]'::jsonb,
      '""'::jsonb, '0'::jsonb, 'false'::jsonb
    )
  );

comment on view public.bookable_amenity is
  'Amenities a resident may request a booking on: active, not temporarily closed, '
  'and narrowed to the columns the resident catalogue shows. Runs as the caller '
  '(security_invoker), so RLS applies. Bookable in principle -- not free at a '
  'given time.';

-- ---------------------------------------------------------------------------
-- 2. Grant
--
-- `authenticated`, matching 0019-0023. Not `anon`: the catalogue is not public,
-- and there is no unauthenticated route that reads it.
--
-- One note for whoever changes the filter above. `resident_amenities_service`
-- applies the temporary-closure test a second time, in Python, on the column
-- this view still exposes. That is deliberate duplication, not an oversight
-- someone missed: no migration in this directory has been applied to any
-- database yet, so the predicate above has never executed, while the Python one
-- has tests behind it. Change one and change the other.
-- ---------------------------------------------------------------------------

grant select on public.bookable_amenity to authenticated;
