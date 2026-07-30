-- 0016_amenities.sql
-- The amenity catalogue, its per-amenity settings, booking series and their
-- occurrences, guests, and the booking ledger (charges + financial events).
--
-- Depends on 0010_memberships.sql, 0011_dashboard_core.sql, 0015_money.sql.
-- Numbering: 0004-0009 belong to the auth/security workstream (build plan 1.4).
--
-- ===========================================================================
-- THE FRONTEND HAS TWO AMENITY PRODUCTS. THIS FILE SERVES ONE OF THEM.
--
-- `src/features/amenities/` is a 114-file subsystem: a catalogue, a per-amenity
-- workspace with four tabs (dashboard / approvals / ledger / settings), a
-- reports page, a resident booking flow with multi-day series, and a financial
-- ledger with deposits, refunds and damage deductions.
--
-- `src/data/amenities.js` + `src/store/slices/createAmenitiesSlice.js` is a
-- SECOND, unrelated one: four amenities with ids `a1`-`a4`, a `timing` display
-- string, a `status` of 'Available' | 'Bookable' | 'Open' | 'Under Maintenance',
-- and bookings whose time is the string '07:00 AM - 08:30 AM'. Nothing links the
-- two -- not the ids, not the field names, not the status vocabulary. The
-- resident Amenities screen reads the first; ResidentLandingPage reads the
-- second.
--
-- This file models the first, because it is the one the admin dashboard uses and
-- the one the ERD describes. The second is a shape no backend can serve at the
-- same time as the first -- an amenity cannot have both `capacity: 20` with
-- `timing: '06:00 AM - 10:00 PM'` and a five-group settings object. Raised as
-- DECISIONS_NEEDED E16 and frontend agenda item 14.
--
-- ===========================================================================
-- WHY AN EXCLUSION CONSTRAINT IS NOT ENOUGH, AND WHAT GUARDS OVERLAP INSTEAD
--
-- The ERD's note on amenity_booking_occurrences reads: "Active occurrences for
-- the same amenity must not overlap; enforce with a PostgreSQL time-range
-- exclusion constraint."
--
-- **That is only correct for exclusive amenities.** The gym has capacity 24 and
-- booking mode 'Shared' -- overlapping bookings are the entire point of it.
-- A blanket exclusion constraint would make every shared amenity behave like a
-- single-occupancy room, and `capacity` would become a number nothing reads.
--
-- Overlap is therefore guarded in two places, because neither alone is enough:
--
--   1. An EXCLUDE ... USING gist constraint, scoped `where is_exclusive`. This
--      catches exclusive-vs-exclusive, which is the strict case, and it holds
--      against direct SQL as well as against the API.
--
--   2. A BEFORE trigger for everything an exclusion constraint cannot express.
--      An EXCLUDE predicate is per-row: it cannot say "these two conflict if
--      EITHER of them is exclusive", which is exactly the exclusive-vs-shared
--      rule. Nor can it count occupants against capacity.
--
-- The trigger takes `pg_advisory_xact_lock` on the amenity before it looks, so
-- it is not the racy service-layer check it would otherwise be: two residents
-- booking the last slot of a capacity-1 amenity in the same millisecond
-- serialise, and the second one loses. Bookings for one amenity are low enough
-- volume that serialising them costs nothing.
--
-- ===========================================================================
-- THE CLEANING BUFFER DEFEATS SHARED CAPACITY IN THE FRONTEND. IT DOES NOT HERE.
--
-- `amenityTimeline.js` paints a cleaning buffer after every booking, and
-- `validateBookingSlot` rejects any proposed booking overlapping one -- in
-- shared mode too (amenityBookingsService.js:327-340).
--
-- Follow that through on the seeded gym: mode Shared, capacity 24, buffer 15
-- minutes. An existing 07:00-09:00 booking produces a buffer at 09:00-09:15. A
-- second resident asking for 07:30-09:30 overlaps that buffer and is refused --
-- so is every other overlapping request. **A shared amenity with a non-zero
-- buffer accepts exactly one booking at a time**, and its capacity of 24 can
-- never be reached. The seed data hides this: no two gym bookings overlap.
--
-- Here the buffer blocks only bookings that occupy the amenity EXCLUSIVELY --
-- exclusive-mode amenities, and private bookings on hybrid ones. Between two
-- shared bookings, capacity governs and the buffer does not apply, because a
-- shared amenity is not vacated between them and there is nothing to clean
-- between two people using the gym at once.
--
-- This is a deliberate behavioural difference from the demo and it is flagged
-- rather than buried: DECISIONS_NEEDED E17 (default stated, answer wanted) and
-- agenda item 15.
--
-- ===========================================================================
-- APPROVAL BELONGS TO THE SERIES, NOT TO THE DAY
--
-- `createResidentAmenityBookingSeries` creates N separate booking records for an
-- N-day request, sharing a `bookingGroupId`. `approveAmenityBookingRequest`
-- approves exactly one of them. So a resident asking for the hall on three
-- consecutive days appears in the approvals table three times, and an admin can
-- approve Monday, reject Tuesday and forget Wednesday.
--
-- The ERD splits series from occurrence, which puts approval where it belongs:
-- one request, one decision. GET /amenities/{id}/approvals therefore returns one
-- row per SERIES, carrying the first occurrence's date and time plus `dayCount`
-- and the full `dates` array. Fewer rows than the demo shows, and a three-day
-- request that renders as its first day alone would be misleading -- so the
-- approvals table needs to render `dayCount`. Agenda item 16.
--
-- ===========================================================================
-- FOUR THINGS THE FRONTEND STORES THAT ARE DERIVED HERE
--
--   `pendingRequests`   - the amenity card's amber badge. Stored in the mock as
--                         a constant (the gym says 5; it has one pending
--                         request). A stored count is wrong from the first
--                         approval onwards.
--   `outstandingDues`   - the card's rose badge. Also a constant (the gym says
--                         4800; its charges total 1600). Money that disagrees
--                         with the ledger it is summarising is worse than no
--                         badge.
--   `paymentStatus`     - six values on the ledger row, all reconstructable from
--                         the charges and the events. Same argument as step 7's
--                         `overdue`: a stored status is right until the next
--                         write and silently wrong after it.
--   `completed`         - a booking status the demo stores. It means "approved
--                         and in the past", which is a fact about the clock.
--
-- ===========================================================================
-- FIVE DELIBERATE DEVIATIONS FROM THE ERD, EACH WITH A REASON
--
-- 1. `amenity_settings` replaces `amenity_rules`. The ERD's rules table is
--    versioned (`effective_from` / `effective_to`) and weekday-scoped, and no
--    screen writes either axis. It also models 8 of the ~30 fields the settings
--    tab saves -- nothing for the cleaning buffer, slot duration, waitlist,
--    auto-approval, same-day bookings, guest bookings, recurring bookings,
--    refund policy, damage deposit, closed days, maintenance days, holiday
--    overrides, temporary closure, minimum duration, or the whole maintenance
--    group. One row per amenity holds all of them. `amenity_settings` is a
--    superset of `amenity_rules`, so adding the versioning axis later is one
--    migration, not a rewrite.
--
-- 2. Occurrences store `booking_date date` + `starts_at time` + `ends_at time`,
--    not two `timestamptz`. A timestamptz makes "07:00" mean whatever the
--    server's zone says, and there is no community timezone field anywhere in
--    the product to resolve it against. Opening hours are wall-clock. The
--    generated `tsrange` columns give the exclusion constraint what it needs
--    without inventing a zone.
--
-- 3. `booking_guests` is named `amenity_booking_guests`, to keep every table in
--    this subsystem under one prefix now that there are seven of them.
--
-- 4. `amenities.location` and `amenities.image_url` are added. The card renders
--    an image and the settings form edits a location; neither is in the ERD.
--
-- 5. Occurrence status carries 'blocked' (an administrative reservation) and
--    'pending', which the ERD's occurrence status does not name. A maintenance
--    block is not a booking anybody made, but it occupies the amenity exactly
--    like one, and giving it a separate table would duplicate every conflict
--    rule.
--
-- All five are DECISIONS_NEEDED D7, for the ERD's owner to accept or reject.
--
-- ===========================================================================
-- THE AMENITY LEDGER IS A SECOND MONEY SYSTEM. THAT IS THE ERD'S DESIGN.
--
-- Step 7 built invoices and payments. This file builds `amenity_booking_charges`
-- and `amenity_financial_events`, which track deposits, refunds and damage
-- deductions -- none of which an invoice models. An invoice cannot be partially
-- refunded to a resident's hand, and a security deposit is not revenue.
--
-- The two are linked exactly where the ERD links them: this file finally adds
-- `invoice_line_items.amenity_booking_charge_id`, which 0015 left out on the
-- grounds that a nullable pointer to a table that does not exist yet is a
-- pointer nothing checks. It exists now.
--
-- What is NOT reconciled: the frontend's approval screen shows a resident's
-- outstanding dues by reading `initialPayments` filtered on `userId`
-- (amenityBookingsService.js:61-67) -- that is, per PERSON. Our invoices attach
-- to the UNIT and have no person. The approvals view therefore reports the
-- FLAT's outstanding balance, which is a different number with the same label.
-- DECISIONS_NEEDED E18.
-- ===========================================================================

-- Required by the exclusion constraint: gist over a uuid equality operator.
create extension if not exists btree_gist;

-- ---------------------------------------------------------------------------
-- assert_community_admin -- one implementation of the check every RPC opens
-- with, in this file and in 0015.
--
-- 0015 called it `assert_billing_admin`, which was accurate there and too narrow
-- to reuse. Rather than copy the body under a second name -- the exact mistake
-- 0015's own comment warns about -- `assert_billing_admin` is redefined below to
-- delegate. It keeps its name so nothing that calls it has to change.
-- ---------------------------------------------------------------------------
create or replace function public.assert_community_admin(p_community_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.is_admin()
     or p_community_id not in (select public.current_community_ids()) then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;
end;
$$;

create or replace function public.assert_billing_admin(p_community_id uuid)
returns void
language sql
security definer
set search_path = public
as $$
  select public.assert_community_admin(p_community_id);
$$;

revoke execute on function public.assert_community_admin(uuid) from public, anon, authenticated;
revoke execute on function public.assert_billing_admin(uuid) from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- current_membership_id -- the caller's membership in one community.
--
-- Every write below stamps an actor. Resolving it inline in nineteen functions
-- is nineteen chances to forget the `status = 'active'` clause.
-- ---------------------------------------------------------------------------
create or replace function public.current_membership_id(p_community_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select m.id
    from public.community_memberships m
   where m.community_id = p_community_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
   limit 1;
$$;

revoke execute on function public.current_membership_id(uuid) from public, anon;
grant execute on function public.current_membership_id(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- amenities
--
-- `status` is the stored truth and `isActive` on the wire is derived from it,
-- rather than the other way round: the frontend carries both and keeps them in
-- sync by hand in four places (`normalizeAmenityRecord`, `createAmenity`,
-- `updateAmenity`, `setAmenityActiveStatus`). Two fields that must agree are one
-- field with extra steps.
-- ---------------------------------------------------------------------------
create table if not exists public.amenities (
  id                        uuid primary key default gen_random_uuid(),
  community_id              uuid not null references public.associations(id) on delete cascade,
  name                      text not null,
  description               text not null default '',
  category                  text not null default 'Utility',
  -- Not in the ERD. The settings tab edits it; the card does not show it.
  location                  text not null default '',
  -- Not in the ERD. The card renders an <img> from it and falls back to a
  -- placeholder icon when it is blank, so '' is a supported value, not a gap.
  image_url                 text not null default '',
  capacity                  integer,
  booking_mode              text not null default 'shared',
  approval_required         boolean not null default false,
  status                    text not null default 'active',
  created_by_membership_id  uuid,
  version                   integer not null default 1,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint amenities_mode_ck
    check (booking_mode in ('shared', 'exclusive', 'hybrid')),
  constraint amenities_status_ck
    check (status in ('active', 'inactive')),
  constraint amenities_category_ck
    check (category in ('Sports', 'Fitness', 'Recreation', 'Events', 'Utility')),
  -- Nullable means "no limit" (the Reading Lounge has none). Zero would mean an
  -- amenity nobody can book, which is what `status = 'inactive'` is for.
  constraint amenities_capacity_ck check (capacity is null or capacity > 0),
  constraint amenities_name_ck check (length(trim(name)) > 0),
  constraint amenities_community_name_uq unique (community_id, name),
  constraint amenities_id_community_uq unique (id, community_id),
  constraint amenities_created_by_fk
    foreign key (created_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (created_by_membership_id)
);

create index if not exists amenities_community_idx
  on public.amenities (community_id, status, name);

drop trigger if exists amenities_set_updated_at on public.amenities;
create trigger amenities_set_updated_at
  before update on public.amenities
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- amenity_settings -- deviation 1 in the header.
--
-- One row per amenity, created with the amenity and never separately. Weekdays
-- are stored as ISO day numbers (1 = Monday .. 7 = Sunday) rather than the
-- frontend's English names, because the booking rules are evaluated in SQL and
-- `extract(isodow from ...)` is the only stable way to ask "is the 14th a
-- Monday?" without a locale. The API maps 1 <-> 'Monday'.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_settings (
  amenity_id                        uuid primary key
                                      references public.amenities(id) on delete cascade,
  community_id                      uuid not null references public.associations(id) on delete cascade,

  -- operatingHours
  opening_time                      time not null default '06:00',
  closing_time                      time not null default '22:00',
  slot_duration_minutes             integer not null default 60,
  cleaning_buffer_minutes           integer not null default 0,

  -- bookingSettings (mode and requireAdminApproval live on `amenities`)
  max_active_bookings_per_resident  integer,
  allow_private_booking             boolean not null default false,
  allow_recurring_booking           boolean not null default false,
  allow_guest_booking               boolean not null default true,
  allow_same_day_booking            boolean not null default true,
  enable_waitlist                   boolean not null default false,
  enable_auto_approval              boolean not null default false,

  -- paymentSettings
  booking_fee                       numeric(12, 2) not null default 0,
  security_deposit                  numeric(12, 2) not null default 0,
  late_cancellation_charge          numeric(12, 2) not null default 0,
  damage_deposit                    numeric(12, 2) not null default 0,
  refund_policy                     text not null default '',
  currency_code                     char(3) not null default 'INR',

  -- availabilitySettings
  closed_days                       smallint[] not null default '{}',
  maintenance_days                  smallint[] not null default '{}',
  holiday_overrides                 date[] not null default '{}',
  temporary_closure                 boolean not null default false,
  minimum_booking_duration_minutes  integer not null default 60,
  maximum_booking_duration_minutes  integer not null default 180,
  advance_booking_window_days       integer not null default 30,

  -- maintenanceSettings
  maintenance_interval              text not null default 'Monthly',
  default_maintenance_duration_minutes integer not null default 60,
  auto_block_maintenance_slots      boolean not null default false,
  maintenance_notes                 text not null default '',

  version                           integer not null default 1,
  created_at                        timestamptz not null default now(),
  updated_at                        timestamptz not null default now(),

  -- An amenity that closes before it opens has no bookable minute in the day and
  -- every booking against it fails with a confusing message instead of this one.
  constraint amenity_settings_hours_ck check (closing_time > opening_time),
  constraint amenity_settings_duration_ck
    check (minimum_booking_duration_minutes > 0
           and maximum_booking_duration_minutes >= minimum_booking_duration_minutes),
  constraint amenity_settings_slot_ck check (slot_duration_minutes > 0),
  constraint amenity_settings_buffer_ck check (cleaning_buffer_minutes >= 0),
  constraint amenity_settings_window_ck check (advance_booking_window_days >= 0),
  constraint amenity_settings_limit_ck
    check (max_active_bookings_per_resident is null
           or max_active_bookings_per_resident > 0),
  constraint amenity_settings_money_ck
    check (booking_fee >= 0 and security_deposit >= 0
           and late_cancellation_charge >= 0 and damage_deposit >= 0),
  constraint amenity_settings_interval_ck
    check (maintenance_interval in ('Weekly', 'Monthly', 'Quarterly', 'As Needed')),
  constraint amenity_settings_closed_days_ck
    check (closed_days <@ array[1, 2, 3, 4, 5, 6, 7]::smallint[]),
  constraint amenity_settings_maintenance_days_ck
    check (maintenance_days <@ array[1, 2, 3, 4, 5, 6, 7]::smallint[]),
  constraint amenity_settings_amenity_fk
    foreign key (amenity_id, community_id)
    references public.amenities (id, community_id) on delete cascade
);

drop trigger if exists amenity_settings_set_updated_at on public.amenity_settings;
create trigger amenity_settings_set_updated_at
  before update on public.amenity_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- amenity_booking_series -- one request, whatever number of days it covers.
--
-- `unit_id` is NOT NULL for a resident booking and NULL for an administrative
-- block, which nobody's flat is responsible for. Everything the ledger charges
-- hangs off the unit for the same reason invoices do (0015's header): a resident
-- who moves out mid-refund does not take the deposit with them.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_booking_series (
  id                          uuid primary key default gen_random_uuid(),
  community_id                uuid not null references public.associations(id) on delete cascade,
  amenity_id                  uuid not null,
  unit_id                     uuid,
  requested_by_membership_id  uuid,
  title                       text not null default 'Resident Booking',
  booking_type                text not null default 'resident',
  -- 'resident' when the resident asked, 'admin' when an admin created or blocked
  -- it on their behalf. The approvals tab shows only the first kind, because an
  -- admin does not queue their own override for their own approval.
  source                      text not null default 'resident',
  is_private                  boolean not null default false,
  requires_approval           boolean not null default false,
  guest_count                 integer not null default 0,
  notes                       text,
  -- The admin booking modal offers a per-booking charge override. NULL means
  -- "use the amenity's configured fee"; 0 means "free", and the two are
  -- different answers.
  charge_override             numeric(12, 2),
  status                      text not null default 'pending',
  requested_at                timestamptz not null default now(),
  approved_by_membership_id   uuid,
  approved_at                 timestamptz,
  rejected_by_membership_id   uuid,
  rejected_at                 timestamptz,
  rejection_reason_code       text,
  rejection_reason            text,
  cancelled_at                timestamptz,
  cancellation_reason_code    text,
  cancellation_reason         text,
  -- Administrative block only: which department reserved the slot.
  department                  text,
  version                     integer not null default 1,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now(),
  constraint amenity_series_status_ck
    check (status in ('pending', 'approved', 'confirmed', 'rejected',
                      'cancelled', 'blocked')),
  constraint amenity_series_type_ck
    check (booking_type in ('resident', 'private-event', 'society-event',
                            'maintenance-reservation')),
  constraint amenity_series_source_ck check (source in ('resident', 'admin')),
  constraint amenity_series_guests_ck check (guest_count >= 0),
  constraint amenity_series_override_ck
    check (charge_override is null or charge_override >= 0),
  -- An administrative block belongs to nobody's flat; every other booking must
  -- name one. Getting this wrong would put a deposit refund against a unit that
  -- never booked. Note the test is on `status`, not on `booking_type`: the admin
  -- booking modal offers 'maintenance-reservation' as a type for a booking made
  -- ON BEHALF OF a resident, which does have a flat.
  constraint amenity_series_unit_ck check (
    case when status = 'blocked' then unit_id is null else unit_id is not null end
  ),
  -- A rejection with no reason is an unanswerable support ticket.
  constraint amenity_series_rejection_ck check (
    status <> 'rejected' or rejection_reason_code is not null
  ),
  constraint amenity_series_id_community_uq unique (id, community_id),
  constraint amenity_series_amenity_fk
    foreign key (amenity_id, community_id)
    references public.amenities (id, community_id) on delete cascade,
  constraint amenity_series_unit_fk
    foreign key (unit_id, community_id)
    references public.apartments (id, association_id) on delete cascade,
  constraint amenity_series_requested_by_fk
    foreign key (requested_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (requested_by_membership_id),
  constraint amenity_series_approved_by_fk
    foreign key (approved_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (approved_by_membership_id),
  constraint amenity_series_rejected_by_fk
    foreign key (rejected_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (rejected_by_membership_id)
);

create index if not exists amenity_series_amenity_idx
  on public.amenity_booking_series (amenity_id, status, requested_at desc);
-- Drives the approvals tab and the amenity card's pending badge without
-- scanning decided requests.
create index if not exists amenity_series_pending_idx
  on public.amenity_booking_series (community_id, amenity_id)
  where status = 'pending';
create index if not exists amenity_series_unit_idx
  on public.amenity_booking_series (unit_id, requested_at desc);

drop trigger if exists amenity_series_set_updated_at on public.amenity_booking_series;
create trigger amenity_series_set_updated_at
  before update on public.amenity_booking_series
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- amenity_booking_occurrences -- one row per day the amenity is occupied.
--
-- Deliberately carries no personal data: no name, no notes, no flat. That is
-- what makes the RLS below workable -- a resident may read every occurrence in
-- their community, because seeing that 15:00-17:00 is taken is the whole point
-- of a booking calendar, while the series row that says WHO took it stays
-- private. Row-level security cannot hide a column, so the split has to be
-- structural.
--
-- `is_exclusive` and `buffer_minutes` are denormalised from the series and the
-- settings at write time. Both are inputs to the generated ranges below, and a
-- generated column cannot run a subquery. Copying the buffer also means that
-- changing an amenity's buffer next month does not retroactively invalidate
-- bookings that were legal when they were made.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_booking_occurrences (
  id                          uuid primary key default gen_random_uuid(),
  community_id                uuid not null references public.associations(id) on delete cascade,
  booking_series_id           uuid not null,
  amenity_id                  uuid not null,
  booking_date                date not null,
  starts_at                   time not null,
  ends_at                     time not null,
  is_exclusive                boolean not null default false,
  buffer_minutes              integer not null default 0,
  -- Occupants of a shared amenity, counted against capacity: the resident plus
  -- their guests. Denormalised from the series for the same reason.
  occupant_count              integer not null default 1,
  status                      text not null default 'pending',
  cancelled_at                timestamptz,
  cancelled_by_membership_id  uuid,
  cancellation_reason_code    text,
  cancellation_reason         text,
  cancelled_by_resident       boolean not null default false,
  force_cancelled             boolean not null default false,
  version                     integer not null default 1,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now(),

  -- The booking itself.
  slot tsrange generated always as (
    tsrange(booking_date + starts_at, booking_date + ends_at, '[)')
  ) stored,
  -- The booking plus its cleaning buffer. Only consulted when one side of the
  -- comparison occupies the amenity exclusively -- see the header.
  blocking_slot tsrange generated always as (
    tsrange(booking_date + starts_at,
            booking_date + ends_at + make_interval(mins => buffer_minutes),
            '[)')
  ) stored,

  constraint amenity_occurrence_status_ck
    check (status in ('pending', 'approved', 'confirmed', 'blocked',
                      'rejected', 'cancelled')),
  constraint amenity_occurrence_time_ck check (ends_at > starts_at),
  constraint amenity_occurrence_buffer_ck check (buffer_minutes >= 0),
  constraint amenity_occurrence_occupants_ck check (occupant_count >= 1),
  -- A cancellation with no timestamp cannot be ordered in the audit trail, and
  -- a timestamp with no cancellation is a row that lies about its own state.
  constraint amenity_occurrence_cancelled_ck check (
    (status = 'cancelled') = (cancelled_at is not null)
  ),
  constraint amenity_occurrence_id_community_uq unique (id, community_id),
  constraint amenity_occurrence_series_fk
    foreign key (booking_series_id, community_id)
    references public.amenity_booking_series (id, community_id) on delete cascade,
  constraint amenity_occurrence_amenity_fk
    foreign key (amenity_id, community_id)
    references public.amenities (id, community_id) on delete cascade,
  constraint amenity_occurrence_cancelled_by_fk
    foreign key (cancelled_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (cancelled_by_membership_id),

  -- GUARD 1 OF 2. Exclusive-vs-exclusive, enforced by the index rather than by
  -- anything that can be forgotten. Scoped to exclusive occupancy because a
  -- blanket version would make `capacity` meaningless -- see the header.
  --
  -- 'pending' is inside the predicate on purpose: an unapproved request holds
  -- its slot, exactly as `isAvailabilityBlockingBooking` does in the frontend.
  -- Otherwise two residents are told the hall is free, both wait, and one of
  -- them finds out at approval time.
  constraint amenity_occurrence_exclusive_no_overlap
    exclude using gist (
      amenity_id with =,
      blocking_slot with &&
    ) where (is_exclusive and status not in ('rejected', 'cancelled'))
);

create index if not exists amenity_occurrence_amenity_date_idx
  on public.amenity_booking_occurrences (amenity_id, booking_date, starts_at);
create index if not exists amenity_occurrence_series_idx
  on public.amenity_booking_occurrences (booking_series_id, booking_date);
create index if not exists amenity_occurrence_community_date_idx
  on public.amenity_booking_occurrences (community_id, booking_date desc);

drop trigger if exists amenity_occurrence_set_updated_at on public.amenity_booking_occurrences;
create trigger amenity_occurrence_set_updated_at
  before update on public.amenity_booking_occurrences
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- amenity_booking_guests (ERD: booking_guests) -- deviation 3.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_booking_guests (
  id                 uuid primary key default gen_random_uuid(),
  community_id       uuid not null references public.associations(id) on delete cascade,
  booking_series_id  uuid not null,
  guest_name         text not null,
  phone_e164         text,
  created_at         timestamptz not null default now(),
  constraint amenity_guest_name_ck check (length(trim(guest_name)) > 0),
  constraint amenity_guest_series_fk
    foreign key (booking_series_id, community_id)
    references public.amenity_booking_series (id, community_id) on delete cascade
);

create index if not exists amenity_guest_series_idx
  on public.amenity_booking_guests (booking_series_id);

-- ---------------------------------------------------------------------------
-- amenity_booking_charges -- what a booking owes, one row per kind of charge.
--
-- Charges say what is owed. `amenity_financial_events` says what moved. Neither
-- table stores a balance, so no balance can drift out of agreement with the
-- rows that produce it -- the same rule 0015 applied to `outstanding_amount`,
-- reached here by having nothing to recompute in the first place.
--
-- A deposit is a charge like any other, and it is what makes the ledger a second
-- money system rather than a view over invoices: it is collected, held, partly
-- consumed by damage, and returned. An invoice models none of that.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_booking_charges (
  id                     uuid primary key default gen_random_uuid(),
  community_id           uuid not null references public.associations(id) on delete cascade,
  booking_occurrence_id  uuid not null,
  charge_type            text not null,
  amount                 numeric(12, 2) not null,
  currency_code          char(3) not null default 'INR',
  status                 text not null default 'due',
  description            text,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint amenity_charge_type_ck
    check (charge_type in ('booking', 'deposit', 'additional',
                           'damage', 'late_cancellation')),
  -- 'due' is the only state that counts towards anything. 'waived' and
  -- 'cancelled' keep the row so the ledger can explain why the number changed,
  -- rather than deleting the evidence.
  constraint amenity_charge_status_ck
    check (status in ('due', 'waived', 'cancelled')),
  constraint amenity_charge_amount_ck check (amount >= 0),
  -- One charge of each kind per booking. Two 'deposit' rows would make
  -- "the deposit" a question with two answers.
  constraint amenity_charge_kind_uq unique (booking_occurrence_id, charge_type),
  constraint amenity_charge_id_community_uq unique (id, community_id),
  constraint amenity_charge_occurrence_fk
    foreign key (booking_occurrence_id, community_id)
    references public.amenity_booking_occurrences (id, community_id) on delete cascade
);

create index if not exists amenity_charge_occurrence_idx
  on public.amenity_booking_charges (booking_occurrence_id);

drop trigger if exists amenity_charge_set_updated_at on public.amenity_booking_charges;
create trigger amenity_charge_set_updated_at
  before update on public.amenity_booking_charges
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- amenity_financial_events -- append-only. Every rupee that moved, and why.
--
-- No `updated_at`, and the RLS below grants SELECT and INSERT only, to admins
-- included. This is the table the ledger's audit timeline is built from, and an
-- audit trail that can be edited is decoration.
-- ---------------------------------------------------------------------------
create table if not exists public.amenity_financial_events (
  id                   uuid primary key default gen_random_uuid(),
  community_id         uuid not null references public.associations(id) on delete cascade,
  booking_charge_id    uuid not null,
  actor_membership_id  uuid,
  event_type           text not null,
  amount               numeric(12, 2) not null,
  currency_code        char(3) not null default 'INR',
  payment_reference    text,
  reason               text,
  notes                text,
  metadata             jsonb not null default '{}'::jsonb,
  created_at           timestamptz not null default now(),
  constraint amenity_event_type_ck
    check (event_type in ('payment', 'refund', 'damage_deduction', 'waiver')),
  constraint amenity_event_amount_ck check (amount > 0),
  constraint amenity_event_charge_fk
    foreign key (booking_charge_id, community_id)
    references public.amenity_booking_charges (id, community_id) on delete cascade,
  constraint amenity_event_actor_fk
    foreign key (actor_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (actor_membership_id)
);

create index if not exists amenity_event_charge_idx
  on public.amenity_financial_events (booking_charge_id, created_at);

-- ---------------------------------------------------------------------------
-- The link 0015 promised. Its comment there:
--
--   "`amenity_booking_charge_id` from the ERD is NOT added yet: the table it
--    references arrives in step 8, and a nullable column with no foreign key is
--    a pointer nothing checks. It is a one-line ALTER when amenities land."
--
-- It is two lines, because the composite key carries the community with it and
-- makes an invoice line pointing at another tenant's charge impossible.
-- ---------------------------------------------------------------------------
alter table public.invoice_line_items
  add column if not exists amenity_booking_charge_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'invoice_line_items_amenity_charge_fk'
  ) then
    alter table public.invoice_line_items
      add constraint invoice_line_items_amenity_charge_fk
      foreign key (amenity_booking_charge_id, community_id)
      references public.amenity_booking_charges (id, community_id)
      on delete set null (amenity_booking_charge_id);
  end if;
end;
$$;

-- ===========================================================================
-- GUARD 2 OF 2 -- the mode-aware overlap and capacity check.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- amenity_occurrence_guard
--
-- Runs BEFORE INSERT and before any UPDATE that could move a booking or revive
-- it. What it enforces, and why none of it fits in the exclusion constraint:
--
--   * Exclusive vs shared. An EXCLUDE predicate is evaluated per row and cannot
--     express "conflict if EITHER side is exclusive".
--   * Capacity. An exclusion constraint compares pairs; it cannot count.
--   * The buffer rule. The buffer applies between exclusive uses and not between
--     shared ones, which is a property of the pair, not of a row.
--
-- pg_advisory_xact_lock makes this a real constraint rather than an optimistic
-- one. Without it, two concurrent transactions both read a free amenity and both
-- insert -- the classic check-then-act race, which is exactly the failure a
-- service-layer check would have. The lock is held to the end of the
-- transaction and is scoped to one amenity, so bookings for different amenities
-- never queue behind each other.
-- ---------------------------------------------------------------------------
create or replace function public.amenity_occurrence_guard()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_capacity   integer;
  v_conflict   record;
  v_occupied   integer;
  v_slot       tsrange;
  v_blocking   tsrange;
begin
  -- A cancelled or rejected occurrence occupies nothing. Leaving early also
  -- means a mass cancellation does not take a lock per row.
  if new.status in ('rejected', 'cancelled') then
    return new;
  end if;

  -- The two ranges are recomputed here rather than read from NEW, because
  -- PostgreSQL fills generated columns AFTER before-triggers run: `new.slot` and
  -- `new.blocking_slot` are both NULL at this point, and every `&&` below would
  -- quietly return NULL -- a guard that passes everything while looking like it
  -- checks. The expressions are the same ones the column definitions use.
  v_slot     := tsrange(new.booking_date + new.starts_at,
                        new.booking_date + new.ends_at, '[)');
  v_blocking := tsrange(new.booking_date + new.starts_at,
                        new.booking_date + new.ends_at
                          + make_interval(mins => new.buffer_minutes), '[)');

  perform pg_advisory_xact_lock(hashtextextended(new.amenity_id::text, 0));

  select a.capacity into v_capacity
    from public.amenities a
   where a.id = new.amenity_id;

  -- Rule 1: anything exclusive on either side conflicts, buffer included.
  select o.id, o.booking_date, o.starts_at, o.ends_at, o.is_exclusive
    into v_conflict
    from public.amenity_booking_occurrences o
   where o.amenity_id = new.amenity_id
     and o.id is distinct from new.id
     and o.status not in ('rejected', 'cancelled')
     and (o.is_exclusive or new.is_exclusive)
     and o.blocking_slot && v_blocking
   limit 1;

  if found then
    raise exception
      'That time is already taken (% %-%). Choose another slot.',
      v_conflict.booking_date, v_conflict.starts_at, v_conflict.ends_at
      using errcode = 'HB409';
  end if;

  -- Rule 2: shared against shared -- capacity, and no buffer between them.
  -- The buffer is skipped here deliberately; see the header. `slot` rather than
  -- `blocking_slot` is what makes that true.
  if not new.is_exclusive and v_capacity is not null then
    select coalesce(sum(o.occupant_count), 0) into v_occupied
      from public.amenity_booking_occurrences o
     where o.amenity_id = new.amenity_id
       and o.id is distinct from new.id
       and o.status not in ('rejected', 'cancelled')
       and not o.is_exclusive
       and o.slot && v_slot;

    if v_occupied + new.occupant_count > v_capacity then
      raise exception
        'That slot is full: % of % places are taken.', v_occupied, v_capacity
        using errcode = 'HB409';
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists amenity_occurrence_guard_trg on public.amenity_booking_occurrences;
create trigger amenity_occurrence_guard_trg
  before insert or update of booking_date, starts_at, ends_at, status,
                             is_exclusive, occupant_count, buffer_minutes
  on public.amenity_booking_occurrences
  for each row execute function public.amenity_occurrence_guard();

-- ===========================================================================
-- VIEWS
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- amenity_overview -- the catalogue card, with both of its badges derived.
--
-- `security_invoker = true` (PG15+) so the view is filtered by the CALLER's RLS
-- rather than the owner's; without it the view is a hole through the policies
-- below. Same reasoning as 0015's three views.
--
-- `pending_requests` and `outstanding_dues` are computed here rather than stored
-- because the mock stores them as constants that never move: the gym card claims
-- 5 pending requests against 1 real one, and 4800 in dues against 1600 in
-- charges. A badge that disagrees with the tab it links to is worse than no
-- badge.
-- ---------------------------------------------------------------------------
create or replace view public.amenity_overview
with (security_invoker = true) as
select
  a.id,
  a.community_id,
  a.name,
  a.description,
  a.category,
  a.location,
  a.image_url,
  a.capacity,
  a.booking_mode,
  a.approval_required,
  a.status,
  (a.status = 'active') as is_active,
  a.version,
  a.created_at,
  a.updated_at,
  s.opening_time,
  s.closing_time,
  s.slot_duration_minutes,
  s.cleaning_buffer_minutes,
  s.max_active_bookings_per_resident,
  s.allow_private_booking,
  s.allow_recurring_booking,
  s.allow_guest_booking,
  s.allow_same_day_booking,
  s.enable_waitlist,
  s.enable_auto_approval,
  s.booking_fee,
  s.security_deposit,
  s.late_cancellation_charge,
  s.damage_deposit,
  s.refund_policy,
  s.currency_code,
  s.closed_days,
  s.maintenance_days,
  s.holiday_overrides,
  s.temporary_closure,
  s.minimum_booking_duration_minutes,
  s.maximum_booking_duration_minutes,
  s.advance_booking_window_days,
  s.maintenance_interval,
  s.default_maintenance_duration_minutes,
  s.auto_block_maintenance_slots,
  s.maintenance_notes,
  coalesce(pending.request_count, 0) as pending_requests,
  coalesce(dues.outstanding_dues, 0) as outstanding_dues,
  lower(concat_ws(' ', a.name, a.description, a.category, a.location))
    as search_text
from public.amenities a
left join public.amenity_settings s on s.amenity_id = a.id
left join lateral (
  select count(*) as request_count
    from public.amenity_booking_series b
   where b.amenity_id = a.id and b.status = 'pending'
) pending on true
-- Everything charged against this amenity's bookings, minus everything paid
-- towards it. Summed in numeric by Postgres, never in the service layer.
left join lateral (
  select greatest(coalesce(sum(c.amount), 0) - coalesce(sum(paid.total), 0), 0)
           as outstanding_dues
    from public.amenity_booking_charges c
    join public.amenity_booking_occurrences o
      on o.id = c.booking_occurrence_id
    left join lateral (
      select coalesce(sum(e.amount), 0) as total
        from public.amenity_financial_events e
       where e.booking_charge_id = c.id and e.event_type = 'payment'
    ) paid on true
   where o.amenity_id = a.id
     and c.status = 'due'
     and o.status not in ('rejected', 'cancelled')
) dues on true;

-- ---------------------------------------------------------------------------
-- amenity_booking_overview -- one row per occupied day, joined to its request.
--
-- This is what the timeline, the resident's booking list and the reports page
-- all read. `status` is the occurrence's, except that 'completed' is derived:
-- an approved booking whose end time has passed is completed, and storing that
-- would need a scheduled job to stay true -- the same argument that kept
-- `overdue` out of the invoices table in 0015.
-- ---------------------------------------------------------------------------
create or replace view public.amenity_booking_overview
with (security_invoker = true) as
select
  o.id,
  o.community_id,
  o.booking_series_id,
  o.amenity_id,
  am.name              as amenity_name,
  am.booking_mode,
  o.booking_date,
  o.starts_at,
  o.ends_at,
  o.is_exclusive,
  o.buffer_minutes,
  o.occupant_count,
  -- "Approved and in the past" -- see the header. The comparison is against UTC
  -- because there is no community timezone field anywhere in the product to
  -- compare against instead, so a booking is treated as finished up to the
  -- server's offset late. It is stated rather than hidden: DECISIONS_NEEDED E19.
  case
    when o.status in ('approved', 'confirmed')
     and (o.booking_date + o.ends_at) < (now() at time zone 'utc')
    then 'completed'
    else o.status
  end                  as status,
  o.status             as stored_status,
  o.cancelled_at,
  o.cancellation_reason_code,
  o.cancellation_reason,
  o.cancelled_by_resident,
  o.force_cancelled,
  o.version,
  o.created_at,
  o.updated_at,
  b.title,
  b.booking_type,
  b.source,
  b.is_private,
  b.requires_approval,
  b.guest_count,
  b.notes,
  b.charge_override,
  b.department,
  b.status             as series_status,
  b.requested_at,
  b.approved_at,
  b.rejected_at,
  b.rejection_reason,
  b.rejection_reason_code,
  b.unit_id,
  ap.code              as unit_code,
  nullif(split_part(ap.code, '-', 1), ap.code) as tower,
  b.requested_by_membership_id,
  res.profile_id       as resident_profile_id,
  res.display_name     as resident_name,
  -- The number of days in the request this occurrence belongs to. One click
  -- approves all of them, so the approvals table has to be able to say so.
  grp.day_count,
  lower(concat_ws(' ', b.title, am.name, ap.code, res.display_name))
    as search_text
from public.amenity_booking_occurrences o
join public.amenity_booking_series b on b.id = o.booking_series_id
join public.amenities am on am.id = o.amenity_id
left join public.apartments ap on ap.id = b.unit_id
left join lateral (
  select m.profile_id, p.full_name as display_name
    from public.community_memberships m
    join public.profiles p on p.id = m.profile_id
   where m.id = b.requested_by_membership_id
) res on true
left join lateral (
  select count(*) as day_count
    from public.amenity_booking_occurrences x
   where x.booking_series_id = o.booking_series_id
     and x.status not in ('rejected', 'cancelled')
) grp on true;

-- ---------------------------------------------------------------------------
-- amenity_ledger_overview -- the ledger row, reconstructed from charges and
-- events.
--
-- Every figure the ledger table renders is here, computed the way
-- `amenityLedgerModel.js` computes it, in numeric rather than in JavaScript:
--
--   totalAmount        = booking + additional charges
--   amountPaid         = payments towards those (deposits excluded, matching
--                        the mock: txn-gym-1001 pays 1100 against 1000 + 100)
--   outstandingDeposit = deposit charged - deposit paid
--   remainingRefund    = deposit paid - damage taken - already refunded
--
-- `payment_status` is derived rather than stored -- see the header. The order of
-- the CASE arms is the meaning: a cancelled booking holding a refundable deposit
-- is 'refund_pending', not 'cancelled', because somebody is still owed money.
-- ---------------------------------------------------------------------------
create or replace view public.amenity_ledger_overview
with (security_invoker = true) as
with charge_totals as (
  select
    c.booking_occurrence_id,
    sum(c.amount) filter (where c.charge_type = 'deposit')       as deposit_amount,
    sum(c.amount) filter (where c.charge_type = 'booking')        as booking_charges,
    sum(c.amount) filter (
      where c.charge_type in ('additional', 'late_cancellation')
    )                                                             as additional_charges,
    sum(paid.total) filter (where c.charge_type = 'deposit')      as deposit_paid,
    sum(paid.total) filter (where c.charge_type <> 'deposit')     as amount_paid,
    sum(refunded.total)                                           as refund_amount,
    sum(damaged.total)                                            as damage_amount,
    max(paid.reference)                                           as payment_reference
  from public.amenity_booking_charges c
  left join lateral (
    select coalesce(sum(e.amount), 0) as total, max(e.payment_reference) as reference
      from public.amenity_financial_events e
     where e.booking_charge_id = c.id and e.event_type = 'payment'
  ) paid on true
  left join lateral (
    select coalesce(sum(e.amount), 0) as total
      from public.amenity_financial_events e
     where e.booking_charge_id = c.id and e.event_type = 'refund'
  ) refunded on true
  left join lateral (
    select coalesce(sum(e.amount), 0) as total
      from public.amenity_financial_events e
     where e.booking_charge_id = c.id and e.event_type = 'damage_deduction'
  ) damaged on true
  where c.status = 'due'
  group by c.booking_occurrence_id
),
rows_with_money as (
  select
    v.*,
    coalesce(t.deposit_amount, 0)     as deposit_amount,
    coalesce(t.deposit_paid, 0)       as deposit_paid,
    coalesce(t.booking_charges, 0)    as booking_charges,
    coalesce(t.additional_charges, 0) as additional_charges,
    coalesce(t.amount_paid, 0)        as amount_paid,
    coalesce(t.refund_amount, 0)      as refund_amount,
    coalesce(t.damage_amount, 0)      as damage_amount,
    t.payment_reference
  from public.amenity_booking_overview v
  left join charge_totals t on t.booking_occurrence_id = v.id
)
select
  r.id,
  r.community_id,
  r.id                as booking_id,
  r.booking_series_id,
  r.amenity_id,
  r.amenity_name,
  r.unit_id,
  r.unit_code,
  r.resident_profile_id,
  r.resident_name,
  r.requested_by_membership_id,
  r.booking_date,
  r.starts_at,
  r.ends_at,
  r.booking_type,
  r.title,
  r.notes,
  r.status            as booking_status,
  r.force_cancelled,
  r.cancelled_at,
  r.cancellation_reason,
  r.approved_at,
  r.created_at,
  r.updated_at,
  r.payment_reference,
  r.deposit_amount,
  r.deposit_paid,
  r.booking_charges,
  r.additional_charges,
  r.amount_paid,
  r.refund_amount,
  r.damage_amount,
  (r.booking_charges + r.additional_charges)                       as total_amount,
  greatest(r.deposit_amount - r.deposit_paid, 0)                   as outstanding_deposit,
  greatest(r.deposit_paid - r.damage_amount - r.refund_amount, 0)  as remaining_refund,
  case
    when greatest(r.deposit_paid - r.damage_amount - r.refund_amount, 0) > 0
     and r.status in ('completed', 'cancelled')            then 'refund_pending'
    when r.status in ('cancelled', 'rejected')
     and r.amount_paid = 0 and r.deposit_paid = 0          then 'cancelled'
    when r.status = 'blocked'                              then 'cancelled'
    when r.refund_amount > 0                               then 'refunded'
    when r.booking_charges + r.additional_charges > 0
     and r.amount_paid >= r.booking_charges + r.additional_charges
                                                           then 'paid'
    when r.amount_paid > 0 or r.deposit_paid > 0           then 'partially_paid'
    else 'pending'
  end                                                              as payment_status
from rows_with_money r;

-- ---------------------------------------------------------------------------
-- amenity_ledger_summary -- the eight figures on the ledger tab, per amenity.
--
-- A database aggregate for the reason 0015 gave: money summed once, in numeric,
-- over every row rather than over the page the client happens to be holding.
-- ---------------------------------------------------------------------------
create or replace view public.amenity_ledger_summary
with (security_invoker = true) as
select
  l.community_id,
  l.amenity_id,
  count(*)                                                as total_bookings,
  coalesce(sum(l.amount_paid), 0)                         as total_revenue,
  coalesce(sum(l.outstanding_deposit), 0)                 as pending_deposits,
  count(*) filter (where l.payment_status = 'refund_pending')
                                                          as refund_pending,
  coalesce(sum(l.refund_amount), 0)                       as refund_completed,
  coalesce(sum(l.damage_amount), 0)                       as damage_deductions,
  coalesce(sum(l.remaining_refund) filter (
    where l.payment_status = 'refund_pending'
  ), 0)                                                   as outstanding_refunds,
  count(*) filter (where l.booking_status = 'completed')  as completed_transactions
from public.amenity_ledger_overview l
group by l.community_id, l.amenity_id;

-- ===========================================================================
-- FUNCTIONS
--
-- Same reason as 0012 and 0015: PostgREST has no client-side transaction, so
-- every .table(...).insert() is its own. A booking request writes a series AND
-- its occurrences AND its guests AND its charges; a refund writes an event AND
-- has to re-derive what is left. Half of either is worse than none of it.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- save_amenity -- create or update, settings included.
--
-- One function rather than two because the settings tab saves the catalogue
-- fields and the five settings groups in a single click, and splitting that
-- across two PostgREST calls would let the second one fail after the first
-- succeeded.
-- ---------------------------------------------------------------------------
create or replace function public.save_amenity(
  p_community_id uuid,
  p_amenity_id   uuid,
  p_payload      jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id      uuid;
  v_actor   uuid;
  v_status  text;
begin
  perform public.assert_community_admin(p_community_id);
  v_actor := public.current_membership_id(p_community_id);

  v_status := case
    when p_payload ? 'is_active'
    then case when (p_payload ->> 'is_active')::boolean then 'active' else 'inactive' end
    else coalesce(nullif(p_payload ->> 'status', ''), 'active')
  end;

  if p_amenity_id is null then
    insert into public.amenities (
      community_id, name, description, category, location, image_url,
      capacity, booking_mode, approval_required, status, created_by_membership_id
    )
    values (
      p_community_id,
      trim(p_payload ->> 'name'),
      coalesce(p_payload ->> 'description', ''),
      coalesce(nullif(p_payload ->> 'category', ''), 'Utility'),
      coalesce(p_payload ->> 'location', ''),
      coalesce(p_payload ->> 'image_url', ''),
      nullif(p_payload ->> 'capacity', '')::integer,
      coalesce(nullif(p_payload ->> 'booking_mode', ''), 'shared'),
      coalesce((p_payload ->> 'approval_required')::boolean, false),
      v_status,
      v_actor
    )
    returning id into v_id;

    insert into public.amenity_settings (amenity_id, community_id)
    values (v_id, p_community_id);
  else
    v_id := p_amenity_id;

    update public.amenities a
       set name              = coalesce(nullif(trim(p_payload ->> 'name'), ''), a.name),
           description       = coalesce(p_payload ->> 'description', a.description),
           category          = coalesce(nullif(p_payload ->> 'category', ''), a.category),
           location          = coalesce(p_payload ->> 'location', a.location),
           image_url         = coalesce(p_payload ->> 'image_url', a.image_url),
           capacity          = case when p_payload ? 'capacity'
                                    then nullif(p_payload ->> 'capacity', '')::integer
                                    else a.capacity end,
           booking_mode      = coalesce(nullif(p_payload ->> 'booking_mode', ''), a.booking_mode),
           approval_required = coalesce((p_payload ->> 'approval_required')::boolean,
                                        a.approval_required),
           status            = v_status,
           version           = a.version + 1
     where a.id = v_id and a.community_id = p_community_id;

    if not found then
      raise exception 'Amenity not found.' using errcode = 'HB404';
    end if;

    -- Lazily, so an amenity created by another workstream is never missing one.
    insert into public.amenity_settings (amenity_id, community_id)
    values (v_id, p_community_id)
    on conflict (amenity_id) do nothing;
  end if;

  -- Every settings key is optional: the catalogue form sends none of them and
  -- the settings tab sends all of them, and both have to work.
  if p_payload ? 'settings' then
    update public.amenity_settings s
       set opening_time = coalesce((p_payload #>> '{settings,opening_time}')::time,
                                   s.opening_time),
           closing_time = coalesce((p_payload #>> '{settings,closing_time}')::time,
                                   s.closing_time),
           slot_duration_minutes = coalesce(
             (p_payload #>> '{settings,slot_duration_minutes}')::integer,
             s.slot_duration_minutes),
           cleaning_buffer_minutes = coalesce(
             (p_payload #>> '{settings,cleaning_buffer_minutes}')::integer,
             s.cleaning_buffer_minutes),
           max_active_bookings_per_resident = case
             when p_payload #> '{settings,max_active_bookings_per_resident}' is not null
             then nullif(p_payload #>> '{settings,max_active_bookings_per_resident}', '')::integer
             else s.max_active_bookings_per_resident end,
           allow_private_booking = coalesce(
             (p_payload #>> '{settings,allow_private_booking}')::boolean,
             s.allow_private_booking),
           allow_recurring_booking = coalesce(
             (p_payload #>> '{settings,allow_recurring_booking}')::boolean,
             s.allow_recurring_booking),
           allow_guest_booking = coalesce(
             (p_payload #>> '{settings,allow_guest_booking}')::boolean,
             s.allow_guest_booking),
           allow_same_day_booking = coalesce(
             (p_payload #>> '{settings,allow_same_day_booking}')::boolean,
             s.allow_same_day_booking),
           enable_waitlist = coalesce(
             (p_payload #>> '{settings,enable_waitlist}')::boolean, s.enable_waitlist),
           enable_auto_approval = coalesce(
             (p_payload #>> '{settings,enable_auto_approval}')::boolean,
             s.enable_auto_approval),
           booking_fee = coalesce(
             (p_payload #>> '{settings,booking_fee}')::numeric, s.booking_fee),
           security_deposit = coalesce(
             (p_payload #>> '{settings,security_deposit}')::numeric, s.security_deposit),
           late_cancellation_charge = coalesce(
             (p_payload #>> '{settings,late_cancellation_charge}')::numeric,
             s.late_cancellation_charge),
           damage_deposit = coalesce(
             (p_payload #>> '{settings,damage_deposit}')::numeric, s.damage_deposit),
           refund_policy = coalesce(p_payload #>> '{settings,refund_policy}',
                                    s.refund_policy),
           currency_code = coalesce(nullif(p_payload #>> '{settings,currency_code}', ''),
                                    s.currency_code),
           closed_days = coalesce(
             (select array_agg(value::smallint)
                from jsonb_array_elements_text(p_payload #> '{settings,closed_days}')),
             case when p_payload #> '{settings,closed_days}' is not null
                  then '{}'::smallint[] else s.closed_days end),
           maintenance_days = coalesce(
             (select array_agg(value::smallint)
                from jsonb_array_elements_text(p_payload #> '{settings,maintenance_days}')),
             case when p_payload #> '{settings,maintenance_days}' is not null
                  then '{}'::smallint[] else s.maintenance_days end),
           holiday_overrides = coalesce(
             (select array_agg(value::date)
                from jsonb_array_elements_text(p_payload #> '{settings,holiday_overrides}')),
             case when p_payload #> '{settings,holiday_overrides}' is not null
                  then '{}'::date[] else s.holiday_overrides end),
           temporary_closure = coalesce(
             (p_payload #>> '{settings,temporary_closure}')::boolean,
             s.temporary_closure),
           minimum_booking_duration_minutes = coalesce(
             (p_payload #>> '{settings,minimum_booking_duration_minutes}')::integer,
             s.minimum_booking_duration_minutes),
           maximum_booking_duration_minutes = coalesce(
             (p_payload #>> '{settings,maximum_booking_duration_minutes}')::integer,
             s.maximum_booking_duration_minutes),
           advance_booking_window_days = coalesce(
             (p_payload #>> '{settings,advance_booking_window_days}')::integer,
             s.advance_booking_window_days),
           maintenance_interval = coalesce(
             nullif(p_payload #>> '{settings,maintenance_interval}', ''),
             s.maintenance_interval),
           default_maintenance_duration_minutes = coalesce(
             (p_payload #>> '{settings,default_maintenance_duration_minutes}')::integer,
             s.default_maintenance_duration_minutes),
           auto_block_maintenance_slots = coalesce(
             (p_payload #>> '{settings,auto_block_maintenance_slots}')::boolean,
             s.auto_block_maintenance_slots),
           maintenance_notes = coalesce(p_payload #>> '{settings,maintenance_notes}',
                                        s.maintenance_notes),
           version = s.version + 1
     where s.amenity_id = v_id;
  end if;

  return v_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- set_amenity_status -- the toggle on the catalogue card.
--
-- Separate from save_amenity because the toggle sends one boolean and nothing
-- else, and routing it through a partial update of twelve fields is how a
-- toggle ends up blanking a description.
-- ---------------------------------------------------------------------------
create or replace function public.set_amenity_status(
  p_amenity_id uuid,
  p_is_active  boolean
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid;
begin
  select community_id into v_community from public.amenities where id = p_amenity_id;
  if v_community is null then
    raise exception 'Amenity not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(v_community);

  update public.amenities
     set status  = case when p_is_active then 'active' else 'inactive' end,
         version = version + 1
   where id = p_amenity_id;

  return p_amenity_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- delete_amenity
--
-- The catalogue has a delete button. It is honoured only for an amenity nobody
-- has ever booked; otherwise it is refused in favour of deactivating, because
-- deleting cascades to the bookings, their charges and their financial events --
-- including deposits somebody is still owed. An amenity that vanishes takes the
-- evidence of its refunds with it.
-- ---------------------------------------------------------------------------
create or replace function public.delete_amenity(p_amenity_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid;
  v_bookings  integer;
begin
  select community_id into v_community from public.amenities where id = p_amenity_id;
  if v_community is null then
    raise exception 'Amenity not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(v_community);

  select count(*) into v_bookings
    from public.amenity_booking_occurrences
   where amenity_id = p_amenity_id;

  if v_bookings > 0 then
    raise exception
      'This amenity has % booking(s) on record and cannot be deleted. Deactivate it instead.',
      v_bookings using errcode = 'HB409';
  end if;

  delete from public.amenities where id = p_amenity_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- amenity_charges_for -- the charges a new booking incurs.
--
-- Called from both booking paths so that an admin override and a resident
-- request are priced by the same rules. `charge_override` replaces the booking
-- fee and nothing else: a waived fee does not waive the deposit, because the
-- deposit is not revenue and is coming back.
-- ---------------------------------------------------------------------------
create or replace function public.amenity_charges_for(
  p_occurrence_id   uuid,
  p_community_id    uuid,
  p_amenity_id      uuid,
  p_charge_override numeric
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_fee      numeric(12, 2);
  v_deposit  numeric(12, 2);
  v_currency char(3);
begin
  select coalesce(p_charge_override, s.booking_fee), s.security_deposit, s.currency_code
    into v_fee, v_deposit, v_currency
    from public.amenity_settings s
   where s.amenity_id = p_amenity_id;

  if coalesce(v_fee, 0) > 0 then
    insert into public.amenity_booking_charges (
      community_id, booking_occurrence_id, charge_type, amount, currency_code, description
    )
    values (p_community_id, p_occurrence_id, 'booking', v_fee, v_currency, 'Booking charge');
  end if;

  if coalesce(v_deposit, 0) > 0 then
    insert into public.amenity_booking_charges (
      community_id, booking_occurrence_id, charge_type, amount, currency_code, description
    )
    values (p_community_id, p_occurrence_id, 'deposit', v_deposit, v_currency,
            'Refundable security deposit');
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- assert_resident_booking_rules -- everything in assertResidentBookingRules(),
-- evaluated where it cannot be skipped.
--
-- The frontend applies these on the resident path only; an admin creating a
-- booking calls assertSlotAvailable and nothing else. That asymmetry is kept:
-- an admin blocking the hall for emergency maintenance at 5am, outside opening
-- hours, on a closed day, is doing their job. The conflict rules in the trigger
-- still apply to both, because two things cannot occupy one room whoever booked
-- them.
-- ---------------------------------------------------------------------------
create or replace function public.assert_resident_booking_rules(
  p_amenity_id  uuid,
  p_unit_id     uuid,
  p_date        date,
  p_starts_at   time,
  p_ends_at     time,
  p_is_private  boolean,
  p_guest_count integer,
  p_new_days    integer
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  a         public.amenities%rowtype;
  s         public.amenity_settings%rowtype;
  v_days    integer;
  v_dow     smallint;
  v_minutes integer;
  v_active  integer;
begin
  select * into a from public.amenities where id = p_amenity_id;
  select * into s from public.amenity_settings where amenity_id = p_amenity_id;

  if a.id is null or a.status <> 'active' then
    raise exception 'This amenity is currently unavailable.' using errcode = 'HB409';
  end if;

  v_dow     := extract(isodow from p_date)::smallint;
  v_days    := p_date - current_date;
  v_minutes := extract(epoch from (p_ends_at - p_starts_at))::integer / 60;

  if s.temporary_closure
     or v_dow = any (s.closed_days)
     or v_dow = any (s.maintenance_days)
     or p_date = any (s.holiday_overrides) then
    raise exception 'This amenity is closed on the selected date.' using errcode = 'HB409';
  end if;

  if v_days < 0 then
    raise exception 'Select today or a future date.' using errcode = 'HB409';
  end if;

  if not s.allow_same_day_booking and v_days = 0 then
    raise exception 'Same-day bookings are not allowed for this amenity.'
      using errcode = 'HB409';
  end if;

  if v_days > s.advance_booking_window_days then
    raise exception 'Bookings can only be made % days in advance.',
      s.advance_booking_window_days using errcode = 'HB409';
  end if;

  if p_starts_at < s.opening_time or p_ends_at > s.closing_time then
    raise exception 'This amenity is open from % to %.', s.opening_time, s.closing_time
      using errcode = 'HB409';
  end if;

  if p_is_private
     and not (a.booking_mode = 'exclusive'
              or (a.booking_mode = 'hybrid' and s.allow_private_booking)) then
    raise exception 'Private bookings are not allowed for this amenity.'
      using errcode = 'HB409';
  end if;

  if not p_is_private and a.booking_mode = 'exclusive' then
    raise exception 'This amenity only supports private bookings.' using errcode = 'HB409';
  end if;

  if p_guest_count > 0 and not s.allow_guest_booking then
    raise exception 'Guest bookings are not allowed for this amenity.'
      using errcode = 'HB409';
  end if;

  if a.capacity is not null and p_guest_count + 1 > a.capacity then
    raise exception 'This amenity allows up to % people per booking.', a.capacity
      using errcode = 'HB409';
  end if;

  if v_minutes < s.minimum_booking_duration_minutes then
    raise exception 'Bookings must be at least % minutes.',
      s.minimum_booking_duration_minutes using errcode = 'HB409';
  end if;

  if v_minutes > s.maximum_booking_duration_minutes then
    raise exception 'Bookings cannot exceed % minutes.',
      s.maximum_booking_duration_minutes using errcode = 'HB409';
  end if;

  -- The limit counts SERIES, not days, matching the frontend's
  -- `bookingGroupId ?? id` set: a three-day request costs one of your slots.
  if s.max_active_bookings_per_resident is not null then
    select count(distinct b.id) into v_active
      from public.amenity_booking_series b
      join public.amenity_booking_occurrences o on o.booking_series_id = b.id
     where b.unit_id = p_unit_id
       and b.amenity_id = p_amenity_id
       and o.booking_date >= current_date
       and o.status not in ('cancelled', 'rejected');

    if v_active + p_new_days > s.max_active_bookings_per_resident then
      raise exception 'You can have up to % active bookings for this amenity.',
        s.max_active_bookings_per_resident using errcode = 'HB409';
    end if;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- request_amenity_booking -- the resident path. One series, N days.
--
-- Whether it needs approval is decided here rather than sent by the client:
-- `requireAdminApproval and not enableAutoApproval`, read from the amenity's own
-- settings. A client that could choose would be a client that could opt out.
-- ---------------------------------------------------------------------------
create or replace function public.request_amenity_booking(
  p_amenity_id uuid,
  p_payload    jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  a           public.amenities%rowtype;
  s           public.amenity_settings%rowtype;
  v_series    uuid;
  v_unit      uuid;
  v_actor     uuid;
  v_private   boolean;
  v_guests    integer;
  v_approval  boolean;
  v_status    text;
  v_starts    time;
  v_ends      time;
  v_dates     date[];
  v_date      date;
  v_occ       uuid;
  v_guest     jsonb;
begin
  select * into a from public.amenities where id = p_amenity_id;
  if a.id is null then
    raise exception 'Amenity not found.' using errcode = 'HB404';
  end if;
  select * into s from public.amenity_settings where amenity_id = p_amenity_id;

  v_actor := public.current_membership_id(a.community_id);
  if v_actor is null then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  -- The flat the booking is charged to: the caller's own current residency.
  -- Taken from the database rather than the payload, so that a resident cannot
  -- book against somebody else's unit by editing a request.
  select r.unit_id into v_unit
    from public.unit_residencies r
   where r.membership_id = v_actor and r.end_date is null
   order by r.is_primary desc, r.start_date
   limit 1;

  if v_unit is null then
    raise exception 'Only a resident of this community can book an amenity.'
      using errcode = 'HB403';
  end if;

  v_private  := coalesce((p_payload ->> 'is_private')::boolean, false);
  v_guests   := coalesce((p_payload ->> 'guest_count')::integer, 0);
  v_starts   := (p_payload ->> 'starts_at')::time;
  v_ends     := (p_payload ->> 'ends_at')::time;
  v_approval := a.approval_required and not s.enable_auto_approval;
  v_status   := case when v_approval then 'pending' else 'confirmed' end;

  select coalesce(array_agg(distinct value::date order by value::date), '{}'::date[])
    into v_dates
    from jsonb_array_elements_text(coalesce(p_payload -> 'dates', '[]'::jsonb));

  if array_length(v_dates, 1) is null then
    raise exception 'Select at least one booking date.' using errcode = 'HB409';
  end if;

  if array_length(v_dates, 1) > 1 and not s.allow_recurring_booking then
    raise exception 'Multi-day bookings are not allowed for this amenity.'
      using errcode = 'HB409';
  end if;

  -- Validate every day before writing any of them: a three-day request that
  -- half-succeeds leaves a resident holding a booking they did not ask for.
  foreach v_date in array v_dates loop
    perform public.assert_resident_booking_rules(
      p_amenity_id, v_unit, v_date, v_starts, v_ends, v_private, v_guests,
      array_length(v_dates, 1)
    );
  end loop;

  insert into public.amenity_booking_series (
    community_id, amenity_id, unit_id, requested_by_membership_id, title,
    booking_type, source, is_private, requires_approval, guest_count, notes, status
  )
  values (
    a.community_id, p_amenity_id, v_unit, v_actor,
    coalesce(nullif(trim(p_payload ->> 'title'), ''), 'Resident Booking'),
    case when v_private then 'private-event' else 'resident' end,
    'resident', v_private, v_approval, v_guests,
    nullif(trim(p_payload ->> 'notes'), ''), v_status
  )
  returning id into v_series;

  foreach v_date in array v_dates loop
    insert into public.amenity_booking_occurrences (
      community_id, booking_series_id, amenity_id, booking_date, starts_at, ends_at,
      is_exclusive, buffer_minutes, occupant_count, status
    )
    values (
      a.community_id, v_series, p_amenity_id, v_date, v_starts, v_ends,
      (v_private or a.booking_mode = 'exclusive'),
      s.cleaning_buffer_minutes, v_guests + 1, v_status
    )
    returning id into v_occ;

    perform public.amenity_charges_for(v_occ, a.community_id, p_amenity_id, null);
  end loop;

  for v_guest in select * from jsonb_array_elements(coalesce(p_payload -> 'guests', '[]'::jsonb))
  loop
    insert into public.amenity_booking_guests (
      community_id, booking_series_id, guest_name, phone_e164
    )
    values (a.community_id, v_series, trim(v_guest ->> 'name'),
            nullif(trim(v_guest ->> 'phone'), ''));
  end loop;

  return v_series;
end;
$$;

-- ---------------------------------------------------------------------------
-- create_admin_amenity_booking -- the admin override.
--
-- Confirmed on creation, never pending: an admin does not queue a booking for
-- their own approval. `assert_resident_booking_rules` is deliberately NOT called
-- -- see its comment. The conflict trigger still runs.
-- ---------------------------------------------------------------------------
create or replace function public.create_admin_amenity_booking(
  p_amenity_id uuid,
  p_payload    jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  a         public.amenities%rowtype;
  s         public.amenity_settings%rowtype;
  v_series  uuid;
  v_occ     uuid;
  v_actor   uuid;
  v_unit    uuid;
  v_private boolean;
  v_guests  integer;
  v_type    text;
  v_guest   jsonb;
begin
  select * into a from public.amenities where id = p_amenity_id;
  if a.id is null then
    raise exception 'Amenity not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(a.community_id);
  select * into s from public.amenity_settings where amenity_id = p_amenity_id;

  v_actor   := public.current_membership_id(a.community_id);
  v_private := coalesce((p_payload ->> 'is_private')::boolean, false);
  v_guests  := coalesce((p_payload ->> 'guest_count')::integer, 0);
  v_type    := coalesce(nullif(p_payload ->> 'booking_type', ''), 'resident');

  -- Resolved from the resident the admin picked, so the ledger charges the flat
  -- and not the person -- the rule 0015 is built around.
  select r.unit_id into v_unit
    from public.unit_residencies r
   where r.membership_id = (p_payload ->> 'membership_id')::uuid
     and r.end_date is null
   order by r.is_primary desc, r.start_date
   limit 1;

  if v_unit is null then
    raise exception 'That resident has no active flat in this community.'
      using errcode = 'HB409';
  end if;

  insert into public.amenity_booking_series (
    community_id, amenity_id, unit_id, requested_by_membership_id, title,
    booking_type, source, is_private, requires_approval, guest_count, notes,
    charge_override, status, approved_by_membership_id, approved_at
  )
  values (
    a.community_id, p_amenity_id, v_unit,
    (p_payload ->> 'membership_id')::uuid,
    coalesce(nullif(trim(p_payload ->> 'title'), ''), 'Resident Booking'),
    v_type, 'admin', v_private, false, v_guests,
    nullif(trim(p_payload ->> 'notes'), ''),
    nullif(p_payload ->> 'charge_override', '')::numeric,
    'confirmed', v_actor, now()
  )
  returning id into v_series;

  insert into public.amenity_booking_occurrences (
    community_id, booking_series_id, amenity_id, booking_date, starts_at, ends_at,
    is_exclusive, buffer_minutes, occupant_count, status
  )
  values (
    a.community_id, v_series, p_amenity_id,
    (p_payload ->> 'booking_date')::date,
    (p_payload ->> 'starts_at')::time,
    (p_payload ->> 'ends_at')::time,
    (v_private or v_type = 'private-event' or a.booking_mode = 'exclusive'),
    s.cleaning_buffer_minutes, v_guests + 1, 'confirmed'
  )
  returning id into v_occ;

  perform public.amenity_charges_for(
    v_occ, a.community_id, p_amenity_id,
    nullif(p_payload ->> 'charge_override', '')::numeric
  );

  for v_guest in select * from jsonb_array_elements(coalesce(p_payload -> 'guests', '[]'::jsonb))
  loop
    insert into public.amenity_booking_guests (
      community_id, booking_series_id, guest_name, phone_e164
    )
    values (a.community_id, v_series, trim(v_guest ->> 'name'),
            nullif(trim(v_guest ->> 'phone'), ''));
  end loop;

  return v_series;
end;
$$;

-- ---------------------------------------------------------------------------
-- block_amenity_slot -- an administrative reservation.
--
-- Not a booking anybody made, but it occupies the amenity exactly like one, so
-- it lives in the same tables and goes through the same conflict trigger. It is
-- always exclusive: a hall closed for repairs is closed to everybody, whatever
-- its booking mode says. It carries no unit and no charges.
-- ---------------------------------------------------------------------------
create or replace function public.block_amenity_slot(
  p_amenity_id uuid,
  p_payload    jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  a        public.amenities%rowtype;
  v_series uuid;
  v_actor  uuid;
  v_reason text;
begin
  select * into a from public.amenities where id = p_amenity_id;
  if a.id is null then
    raise exception 'Amenity not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(a.community_id);

  v_actor  := public.current_membership_id(a.community_id);
  v_reason := nullif(trim(p_payload ->> 'reason'), '');

  if v_reason is null then
    raise exception 'A reason is required to block a slot.' using errcode = 'HB409';
  end if;

  insert into public.amenity_booking_series (
    community_id, amenity_id, unit_id, requested_by_membership_id, title,
    booking_type, source, is_private, requires_approval, guest_count, notes,
    department, status, approved_by_membership_id, approved_at
  )
  values (
    a.community_id, p_amenity_id, null, v_actor, v_reason,
    'maintenance-reservation', 'admin', true, false, 0,
    nullif(trim(p_payload ->> 'notes'), ''),
    nullif(trim(p_payload ->> 'department'), ''),
    'blocked', v_actor, now()
  )
  returning id into v_series;

  insert into public.amenity_booking_occurrences (
    community_id, booking_series_id, amenity_id, booking_date, starts_at, ends_at,
    is_exclusive, buffer_minutes, occupant_count, status
  )
  values (
    a.community_id, v_series, p_amenity_id,
    (p_payload ->> 'booking_date')::date,
    (p_payload ->> 'starts_at')::time,
    (p_payload ->> 'ends_at')::time,
    true, 0, 1, 'blocked'
  );

  return v_series;
end;
$$;

-- ---------------------------------------------------------------------------
-- approve_amenity_booking -- one decision for the whole request.
--
-- See the header: the frontend approves one day at a time because it has no
-- series. Here approving a three-day request approves three days, which is what
-- the resident asked for and what the admin thinks they are clicking.
-- ---------------------------------------------------------------------------
create or replace function public.approve_amenity_booking(p_series_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  b       public.amenity_booking_series%rowtype;
  v_actor uuid;
begin
  select * into b from public.amenity_booking_series where id = p_series_id;
  if b.id is null then
    raise exception 'Booking request not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(b.community_id);

  if b.status <> 'pending' then
    raise exception 'This booking request is no longer pending approval.'
      using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(b.community_id);

  update public.amenity_booking_series
     set status = 'approved', approved_by_membership_id = v_actor,
         approved_at = now(), version = version + 1
   where id = p_series_id;

  -- Days the resident already withdrew keep their cancellation. Approving a
  -- request should not resurrect a day somebody said they no longer wanted.
  update public.amenity_booking_occurrences
     set status = 'approved', version = version + 1
   where booking_series_id = p_series_id
     and status = 'pending';

  return p_series_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- reject_amenity_booking
--
-- The reason is mandatory, and 'other' must carry free text -- the frontend
-- enforces both and a rejection with neither is an unanswerable support ticket.
-- Rejecting frees the slot, which is why the occurrences move too: a held slot
-- behind a rejected request is a room nobody can book and nobody is using.
-- ---------------------------------------------------------------------------
create or replace function public.reject_amenity_booking(
  p_series_id uuid,
  p_payload   jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  b        public.amenity_booking_series%rowtype;
  v_actor  uuid;
  v_code   text;
  v_detail text;
begin
  select * into b from public.amenity_booking_series where id = p_series_id;
  if b.id is null then
    raise exception 'Booking request not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(b.community_id);

  if b.status = 'approved' then
    raise exception 'This booking request has already been approved.'
      using errcode = 'HB409';
  end if;
  if b.status <> 'pending' then
    raise exception 'This booking request is no longer pending approval.'
      using errcode = 'HB409';
  end if;

  v_code   := nullif(trim(p_payload ->> 'reason_code'), '');
  v_detail := nullif(trim(p_payload ->> 'reason'), '');

  if v_code is null then
    raise exception 'Select a rejection reason.' using errcode = 'HB409';
  end if;
  if v_code = 'other' and v_detail is null then
    raise exception 'Add the rejection reason.' using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(b.community_id);

  update public.amenity_booking_series
     set status = 'rejected', rejected_by_membership_id = v_actor,
         rejected_at = now(), rejection_reason_code = v_code,
         rejection_reason = coalesce(v_detail, v_code), version = version + 1
   where id = p_series_id;

  update public.amenity_booking_occurrences
     set status = 'rejected', version = version + 1
   where booking_series_id = p_series_id and status = 'pending';

  return p_series_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- cancel_amenity_occurrences -- cancel selected days of a request.
--
-- One function for both callers. A resident may withdraw their own future days
-- and nothing else; an admin may cancel any day. The check is on what the caller
-- IS, not on a flag they send, so there is no parameter to lie about.
--
-- Cancelling frees the slot the moment it commits, because the conflict rules
-- exclude cancelled rows -- no cleanup pass, nothing to schedule.
-- ---------------------------------------------------------------------------
create or replace function public.cancel_amenity_occurrences(p_payload jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ids       uuid[];
  v_community uuid;
  v_admin     boolean;
  v_actor     uuid;
  v_reason    text;
  v_code      text;
  v_count     integer;
  v_blocked   integer;
begin
  select coalesce(array_agg(value::uuid), '{}'::uuid[]) into v_ids
    from jsonb_array_elements_text(coalesce(p_payload -> 'occurrence_ids', '[]'::jsonb));

  if array_length(v_ids, 1) is null then
    raise exception 'Select at least one booking day to cancel.' using errcode = 'HB409';
  end if;

  -- STRICT, so that a list spanning two communities raises rather than picking
  -- the first row and authorising the whole batch against it. `select into`
  -- without STRICT silently takes row one, which is how a cross-tenant write
  -- gets through a check that looks like it is doing its job.
  begin
    select distinct community_id into strict v_community
      from public.amenity_booking_occurrences where id = any (v_ids);
  exception
    when no_data_found then
      raise exception 'Booking not found.' using errcode = 'HB404';
    when too_many_rows then
      raise exception 'Those bookings are not all in the same community.'
        using errcode = 'HB403';
  end;

  v_admin := public.is_admin()
             and v_community in (select public.current_community_ids());
  v_actor := public.current_membership_id(v_community);

  if not v_admin and v_actor is null then
    raise exception 'Not permitted for this community.' using errcode = 'HB403';
  end if;

  v_code   := coalesce(nullif(trim(p_payload ->> 'reason_code'), ''), 'resident-requested');
  v_reason := nullif(trim(p_payload ->> 'reason'), '');

  if v_code = 'other' and v_reason is null then
    raise exception 'Add details for the cancellation reason.' using errcode = 'HB409';
  end if;
  if not v_admin and v_reason is null then
    raise exception 'Add a cancellation reason.' using errcode = 'HB409';
  end if;

  -- Counted before the update so the caller is told they picked something they
  -- cannot cancel, rather than silently getting fewer cancellations than days.
  -- The `not exists` arm covers an id that matches nothing at all: without it, a
  -- typo'd id is not "blocked", it is simply skipped, and the caller is told
  -- three days were cancelled when two were.
  select count(*) into v_blocked
    from unnest(v_ids) as requested(id)
   where not exists (
     select 1
       from public.amenity_booking_occurrences o
       join public.amenity_booking_series b on b.id = o.booking_series_id
      where o.id = requested.id
        and o.status in ('pending', 'approved', 'confirmed')
        and (v_admin or (
              b.requested_by_membership_id = v_actor
              and o.booking_date >= current_date
            ))
   );

  if v_blocked > 0 then
    raise exception 'One or more selected booking days can no longer be cancelled.'
      using errcode = 'HB409';
  end if;

  update public.amenity_booking_occurrences
     set status = 'cancelled',
         cancelled_at = now(),
         cancelled_by_membership_id = v_actor,
         cancellation_reason_code = v_code,
         cancellation_reason = coalesce(v_reason, v_code),
         cancelled_by_resident = not v_admin,
         version = version + 1
   where id = any (v_ids);

  get diagnostics v_count = row_count;

  -- A request with no live day left is itself cancelled, so the approvals tab
  -- stops offering a decision on something that no longer exists.
  update public.amenity_booking_series b
     set status = 'cancelled', cancelled_at = now(),
         cancellation_reason_code = v_code,
         cancellation_reason = coalesce(v_reason, v_code),
         version = b.version + 1
   where b.id in (
     select distinct o.booking_series_id
       from public.amenity_booking_occurrences o where o.id = any (v_ids)
   )
     and b.status not in ('cancelled', 'rejected')
     and not exists (
       select 1 from public.amenity_booking_occurrences x
        where x.booking_series_id = b.id
          and x.status not in ('cancelled', 'rejected')
     );

  return v_count;
end;
$$;

-- ---------------------------------------------------------------------------
-- force_cancel_amenity_booking -- the ledger's red action.
--
-- Distinct from an ordinary cancellation because it overrides a booking the
-- resident still wants, and the ledger records who did it. It also puts the
-- deposit into refund_pending, which the ledger view derives on its own: nothing
-- here writes a payment status.
-- ---------------------------------------------------------------------------
create or replace function public.force_cancel_amenity_booking(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  o       public.amenity_booking_occurrences%rowtype;
  v_actor uuid;
  v_code  text;
begin
  select * into o from public.amenity_booking_occurrences where id = p_occurrence_id;
  if o.id is null then
    raise exception 'The linked booking could not be found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(o.community_id);

  if o.status not in ('approved', 'confirmed') then
    raise exception 'This booking is no longer eligible for force cancellation.'
      using errcode = 'HB409';
  end if;

  v_code := nullif(trim(p_payload ->> 'reason_code'), '');
  if v_code is null then
    raise exception 'A cancellation reason is required.' using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(o.community_id);

  update public.amenity_booking_occurrences
     set status = 'cancelled', cancelled_at = now(),
         cancelled_by_membership_id = v_actor,
         cancellation_reason_code = v_code,
         cancellation_reason = coalesce(nullif(trim(p_payload ->> 'reason'), ''), v_code),
         cancelled_by_resident = false,
         force_cancelled = true,
         version = version + 1
   where id = p_occurrence_id;

  return p_occurrence_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- record_amenity_payment -- money in, against one kind of charge.
--
-- Refuses more than is owed for the same reason 0015 refuses an overpayment:
-- clamping accepts money and then loses it. Idempotent on `payment_reference`
-- within a charge, so a replayed gateway callback returns rather than
-- double-crediting.
-- ---------------------------------------------------------------------------
create or replace function public.record_amenity_payment(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  o           public.amenity_booking_occurrences%rowtype;
  c           public.amenity_booking_charges%rowtype;
  v_actor     uuid;
  v_amount    numeric(12, 2);
  v_type      text;
  v_reference text;
  v_paid      numeric(12, 2);
  v_event     uuid;
begin
  select * into o from public.amenity_booking_occurrences where id = p_occurrence_id;
  if o.id is null then
    raise exception 'Booking not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(o.community_id);

  v_type      := coalesce(nullif(p_payload ->> 'charge_type', ''), 'booking');
  v_amount    := (p_payload ->> 'amount')::numeric;
  v_reference := nullif(trim(p_payload ->> 'payment_reference'), '');

  if v_amount is null or v_amount <= 0 then
    raise exception 'Enter a payment amount greater than zero.' using errcode = 'HB409';
  end if;

  select * into c
    from public.amenity_booking_charges
   where booking_occurrence_id = p_occurrence_id
     and charge_type = v_type and status = 'due';

  if c.id is null then
    raise exception 'This booking has no outstanding % charge.', v_type
      using errcode = 'HB409';
  end if;

  if v_reference is not null then
    select id into v_event
      from public.amenity_financial_events
     where booking_charge_id = c.id
       and event_type = 'payment'
       and payment_reference = v_reference;

    if v_event is not null then
      return v_event;
    end if;
  end if;

  select coalesce(sum(amount), 0) into v_paid
    from public.amenity_financial_events
   where booking_charge_id = c.id and event_type = 'payment';

  if v_paid + v_amount > c.amount then
    raise exception 'That is more than the % still owed on this charge.',
      c.amount - v_paid using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(o.community_id);

  insert into public.amenity_financial_events (
    community_id, booking_charge_id, actor_membership_id, event_type, amount,
    currency_code, payment_reference, reason, notes
  )
  values (
    o.community_id, c.id, v_actor, 'payment', v_amount, c.currency_code,
    v_reference, nullif(trim(p_payload ->> 'method'), ''),
    nullif(trim(p_payload ->> 'notes'), '')
  )
  returning id into v_event;

  return v_event;
end;
$$;

-- ---------------------------------------------------------------------------
-- refund_amenity_deposit -- return what is left of the deposit.
--
-- The amount is computed here, not accepted from the caller: it is the deposit
-- paid, less damage already taken, less anything already refunded. The frontend
-- computes the same figure and sends nothing (`processDepositRefund` uses
-- `normalized.remainingRefund`), and a refund whose amount is a request
-- parameter is a refund somebody can ask to be larger.
-- ---------------------------------------------------------------------------
create or replace function public.refund_amenity_deposit(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  o         public.amenity_booking_occurrences%rowtype;
  c         public.amenity_booking_charges%rowtype;
  v_actor   uuid;
  v_paid    numeric(12, 2);
  v_damage  numeric(12, 2);
  v_refund  numeric(12, 2);
  v_left    numeric(12, 2);
  v_event   uuid;
begin
  select * into o from public.amenity_booking_occurrences where id = p_occurrence_id;
  if o.id is null then
    raise exception 'Booking not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(o.community_id);

  select * into c
    from public.amenity_booking_charges
   where booking_occurrence_id = p_occurrence_id
     and charge_type = 'deposit' and status = 'due'
     for update;

  if c.id is null then
    raise exception 'This booking has no deposit to refund.' using errcode = 'HB409';
  end if;

  -- A deposit is only refundable once the booking is over or off. Refunding a
  -- booking that is still going to happen leaves the amenity unsecured.
  if not (o.status = 'cancelled'
          or (o.status in ('approved', 'confirmed')
              and (o.booking_date + o.ends_at) < now() at time zone 'utc')) then
    raise exception 'This deposit is no longer eligible for a refund.'
      using errcode = 'HB409';
  end if;

  select
    coalesce(sum(amount) filter (where event_type = 'payment'), 0),
    coalesce(sum(amount) filter (where event_type = 'damage_deduction'), 0),
    coalesce(sum(amount) filter (where event_type = 'refund'), 0)
    into v_paid, v_damage, v_refund
    from public.amenity_financial_events
   where booking_charge_id = c.id;

  v_left := v_paid - v_damage - v_refund;

  if v_left <= 0 then
    raise exception 'This deposit is no longer eligible for a refund.'
      using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(o.community_id);

  insert into public.amenity_financial_events (
    community_id, booking_charge_id, actor_membership_id, event_type, amount,
    currency_code, reason, notes
  )
  values (
    o.community_id, c.id, v_actor, 'refund', v_left, c.currency_code,
    nullif(trim(p_payload ->> 'reason'), ''), nullif(trim(p_payload ->> 'notes'), '')
  )
  returning id into v_event;

  return v_event;
end;
$$;

-- ---------------------------------------------------------------------------
-- deduct_amenity_damage -- take damage out of the held deposit.
--
-- Capped at what is left, and the cap is enforced here rather than trusted from
-- the client: a deduction larger than the deposit is not a deduction, it is an
-- invoice, and it would drive `remaining_refund` negative -- which the ledger
-- view clamps to zero, quietly hiding the error.
-- ---------------------------------------------------------------------------
create or replace function public.deduct_amenity_damage(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  o        public.amenity_booking_occurrences%rowtype;
  c        public.amenity_booking_charges%rowtype;
  v_actor  uuid;
  v_amount numeric(12, 2);
  v_reason text;
  v_paid   numeric(12, 2);
  v_damage numeric(12, 2);
  v_refund numeric(12, 2);
  v_left   numeric(12, 2);
  v_event  uuid;
begin
  select * into o from public.amenity_booking_occurrences where id = p_occurrence_id;
  if o.id is null then
    raise exception 'Booking not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(o.community_id);

  v_amount := (p_payload ->> 'amount')::numeric;
  v_reason := nullif(trim(p_payload ->> 'reason'), '');

  if v_amount is null or v_amount <= 0 then
    raise exception 'Enter a valid damage amount.' using errcode = 'HB409';
  end if;
  if v_reason is null then
    raise exception 'A damage reason is required.' using errcode = 'HB409';
  end if;

  select * into c
    from public.amenity_booking_charges
   where booking_occurrence_id = p_occurrence_id
     and charge_type = 'deposit' and status = 'due'
     for update;

  if c.id is null then
    raise exception 'This booking has no deposit to deduct from.' using errcode = 'HB409';
  end if;

  select
    coalesce(sum(amount) filter (where event_type = 'payment'), 0),
    coalesce(sum(amount) filter (where event_type = 'damage_deduction'), 0),
    coalesce(sum(amount) filter (where event_type = 'refund'), 0)
    into v_paid, v_damage, v_refund
    from public.amenity_financial_events
   where booking_charge_id = c.id;

  v_left := v_paid - v_damage - v_refund;

  if v_left <= 0 then
    raise exception 'This deposit is no longer eligible for damage deductions.'
      using errcode = 'HB409';
  end if;
  if v_amount > v_left then
    raise exception 'Damage deduction cannot exceed the refundable % .', v_left
      using errcode = 'HB409';
  end if;

  v_actor := public.current_membership_id(o.community_id);

  insert into public.amenity_financial_events (
    community_id, booking_charge_id, actor_membership_id, event_type, amount,
    currency_code, reason, notes
  )
  values (
    o.community_id, c.id, v_actor, 'damage_deduction', v_amount, c.currency_code,
    v_reason, nullif(trim(p_payload ->> 'notes'), '')
  )
  returning id into v_event;

  return v_event;
end;
$$;

-- ---------------------------------------------------------------------------
-- amenity_report_totals -- the six KPIs on the reports page.
--
-- A function rather than a view because the reports page filters by date range,
-- amenity and booking status, and a view would have to be filtered by the
-- caller AFTER aggregating -- which is the wrong order and gives the totals of
-- everything.
--
-- It exists at all because the alternative was summing a page of rows in the
-- service layer. `calculateAmenityReports` does exactly that in the browser, and
-- over a community with more bookings than one response holds it reports the
-- revenue of the page: a smaller number, in rupees, with nothing to say so.
-- Same failure as the money tiles (frontend agenda item 11).
-- ---------------------------------------------------------------------------
create or replace function public.amenity_report_totals(
  p_community_id uuid,
  p_payload      jsonb
)
returns table (
  total_amenities       integer,
  active_amenities      integer,
  total_active_bookings integer,
  pending_approvals     integer,
  total_revenue         numeric,
  bookings_this_month   integer
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_from     date := nullif(p_payload ->> 'start_date', '')::date;
  v_to       date := nullif(p_payload ->> 'end_date', '')::date;
  v_amenity  uuid := nullif(p_payload ->> 'amenity_id', '')::uuid;
  v_status   text := nullif(p_payload ->> 'booking_status', '');
  v_month    text := to_char(current_date, 'YYYY-MM');
begin
  perform public.assert_community_admin(p_community_id);

  return query
  with selected as (
    select l.*
      from public.amenity_ledger_overview l
     where l.community_id = p_community_id
       and (v_amenity is null or l.amenity_id = v_amenity)
       and (v_from    is null or l.booking_date >= v_from)
       and (v_to      is null or l.booking_date <= v_to)
       and (v_status  is null or l.booking_status = v_status)
  ),
  -- An administrative block is not a booking anybody made, so it is out of
  -- every count -- but its money, if it somehow has any, is still money.
  countable as (
    select * from selected where booking_status <> 'blocked'
  ),
  scoped as (
    select a.id, a.status
      from public.amenities a
     where a.community_id = p_community_id
       and (
         v_amenity is not null and a.id = v_amenity
         or v_amenity is null and (
              (v_from is null and v_to is null and v_status is null)
              or a.id in (select distinct amenity_id from selected)
            )
       )
  )
  select
    (select count(*)::integer from scoped),
    (select count(*)::integer from scoped where status = 'active'),
    (select count(*)::integer from countable
      where booking_status in ('approved', 'confirmed')),
    (select count(*)::integer from countable where booking_status = 'pending'),
    (select coalesce(sum(amount_paid), 0) from selected),
    (select count(*)::integer from countable
      where to_char(booking_date, 'YYYY-MM') = v_month);
end;
$$;

-- ---------------------------------------------------------------------------
-- add_amenity_charge -- an extra charge after the fact.
--
-- The ledger's `additionalCharges` column: housekeeping billed after an event,
-- a late-cancellation fee. Separate from the booking charge so the ledger can
-- still say what the booking itself cost.
-- ---------------------------------------------------------------------------
create or replace function public.add_amenity_charge(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  o        public.amenity_booking_occurrences%rowtype;
  v_type   text;
  v_amount numeric(12, 2);
  v_id     uuid;
begin
  select * into o from public.amenity_booking_occurrences where id = p_occurrence_id;
  if o.id is null then
    raise exception 'Booking not found.' using errcode = 'HB404';
  end if;
  perform public.assert_community_admin(o.community_id);

  v_type   := coalesce(nullif(p_payload ->> 'charge_type', ''), 'additional');
  v_amount := (p_payload ->> 'amount')::numeric;

  if v_amount is null or v_amount <= 0 then
    raise exception 'Enter a charge amount greater than zero.' using errcode = 'HB409';
  end if;
  if v_type not in ('additional', 'late_cancellation') then
    raise exception 'Only additional and late-cancellation charges can be added.'
      using errcode = 'HB409';
  end if;

  -- A second additional charge ADDS to the first rather than replacing it: the
  -- ledger has one `additionalCharges` figure, and housekeeping billed on Monday
  -- plus a broken chair billed on Tuesday is 'two things', not 'the later one'.
  insert into public.amenity_booking_charges as chg (
    community_id, booking_occurrence_id, charge_type, amount, currency_code, description
  )
  select o.community_id, p_occurrence_id, v_type, v_amount, s.currency_code,
         nullif(trim(p_payload ->> 'description'), '')
    from public.amenity_settings s
   where s.amenity_id = o.amenity_id
  on conflict (booking_occurrence_id, charge_type) do update
    set amount      = chg.amount + excluded.amount,
        description = coalesce(excluded.description, chg.description),
        status      = 'due'
  returning chg.id into v_id;

  return v_id;
end;
$$;

-- Internal helpers: never callable over PostgREST. Only the RPCs above are.
revoke execute on function
  public.amenity_charges_for(uuid, uuid, uuid, numeric),
  public.assert_resident_booking_rules(uuid, uuid, date, time, time, boolean, integer, integer)
  from public, anon, authenticated;

-- ===========================================================================
-- Row-Level Security
--
-- The split between the occurrence table and the series table is what makes
-- this workable. A resident may read EVERY occurrence in their community --
-- otherwise the booking calendar cannot show that 15:00-17:00 is taken -- but
-- occurrences carry no name, no note and no flat. The series row that says who
-- booked it is readable only by its own requester and by admins. RLS cannot
-- hide a column, so the privacy boundary had to be a table boundary.
-- ===========================================================================
alter table public.amenities enable row level security;
alter table public.amenity_settings enable row level security;
alter table public.amenity_booking_series enable row level security;
alter table public.amenity_booking_occurrences enable row level security;
alter table public.amenity_booking_guests enable row level security;
alter table public.amenity_booking_charges enable row level security;
alter table public.amenity_financial_events enable row level security;

drop policy if exists amenities_admin_all on public.amenities;
create policy amenities_admin_all on public.amenities
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- Inactive amenities included: the resident screen renders them greyed out with
-- "disabled by the administrator" rather than making them disappear.
drop policy if exists amenities_member_read on public.amenities;
create policy amenities_member_read on public.amenities
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists amenity_settings_admin_all on public.amenity_settings;
create policy amenity_settings_admin_all on public.amenity_settings
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- Residents read settings because the booking form needs them: opening hours,
-- closed days, the advance window, minimum duration. Withholding them would
-- mean a resident finds out a rule only by breaking it.
drop policy if exists amenity_settings_member_read on public.amenity_settings;
create policy amenity_settings_member_read on public.amenity_settings
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists amenity_series_admin_all on public.amenity_booking_series;
create policy amenity_series_admin_all on public.amenity_booking_series
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists amenity_series_own_read on public.amenity_booking_series;
create policy amenity_series_own_read on public.amenity_booking_series
  for select using (
    exists (
      select 1 from public.community_memberships m
       where m.id = amenity_booking_series.requested_by_membership_id
         and m.profile_id = auth.uid()
    )
  );

drop policy if exists amenity_occurrence_admin_all on public.amenity_booking_occurrences;
create policy amenity_occurrence_admin_all on public.amenity_booking_occurrences
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- Availability is community-wide by design; see the block comment above.
drop policy if exists amenity_occurrence_member_read on public.amenity_booking_occurrences;
create policy amenity_occurrence_member_read on public.amenity_booking_occurrences
  for select using (community_id in (select public.current_community_ids()));

drop policy if exists amenity_guests_admin_all on public.amenity_booking_guests;
create policy amenity_guests_admin_all on public.amenity_booking_guests
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists amenity_guests_own_read on public.amenity_booking_guests;
create policy amenity_guests_own_read on public.amenity_booking_guests
  for select using (
    exists (
      select 1
        from public.amenity_booking_series b
        join public.community_memberships m
          on m.id = b.requested_by_membership_id
       where b.id = amenity_booking_guests.booking_series_id
         and m.profile_id = auth.uid()
    )
  );

drop policy if exists amenity_charges_admin_all on public.amenity_booking_charges;
create policy amenity_charges_admin_all on public.amenity_booking_charges
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

-- A resident sees what their own booking cost, and nobody else's.
drop policy if exists amenity_charges_own_read on public.amenity_booking_charges;
create policy amenity_charges_own_read on public.amenity_booking_charges
  for select using (
    exists (
      select 1
        from public.amenity_booking_occurrences o
        join public.amenity_booking_series b on b.id = o.booking_series_id
        join public.community_memberships m on m.id = b.requested_by_membership_id
       where o.id = amenity_booking_charges.booking_occurrence_id
         and m.profile_id = auth.uid()
    )
  );

-- Append-only, admins included: SELECT and INSERT, no UPDATE, no DELETE. An
-- audit trail that can be edited is decoration.
drop policy if exists amenity_events_admin_read on public.amenity_financial_events;
create policy amenity_events_admin_read on public.amenity_financial_events
  for select using (
    public.is_admin() and community_id in (select public.current_community_ids())
  );

drop policy if exists amenity_events_admin_insert on public.amenity_financial_events;
create policy amenity_events_admin_insert on public.amenity_financial_events
  for insert with check (
    public.is_admin() and community_id in (select public.current_community_ids())
  );

drop policy if exists amenity_events_own_read on public.amenity_financial_events;
create policy amenity_events_own_read on public.amenity_financial_events
  for select using (
    exists (
      select 1
        from public.amenity_booking_charges c
        join public.amenity_booking_occurrences o on o.id = c.booking_occurrence_id
        join public.amenity_booking_series b on b.id = o.booking_series_id
        join public.community_memberships m on m.id = b.requested_by_membership_id
       where c.id = amenity_financial_events.booking_charge_id
         and m.profile_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Verification -- run after applying. Each returns zero rows unless noted.
-- ---------------------------------------------------------------------------
-- All four views are security_invoker (expect four rows, all 'true'):
--   select c.relname, (select option_value from pg_options_to_table(c.reloptions)
--                       where option_name = 'security_invoker')
--   from pg_class c
--   where c.relname in ('amenity_overview', 'amenity_booking_overview',
--                       'amenity_ledger_overview', 'amenity_ledger_summary');
--
-- No two exclusive occupations of one amenity overlap (the exclusion constraint
-- should make this impossible):
--   select a.id, b.id, a.amenity_id, a.blocking_slot, b.blocking_slot
--   from public.amenity_booking_occurrences a
--   join public.amenity_booking_occurrences b
--     on b.amenity_id = a.amenity_id and b.id > a.id
--    and b.blocking_slot && a.blocking_slot
--   where a.is_exclusive and b.is_exclusive
--     and a.status not in ('rejected','cancelled')
--     and b.status not in ('rejected','cancelled');
--
-- No shared slot is over capacity (the trigger should make this impossible):
--   select o.amenity_id, o.slot, sum(x.occupant_count), am.capacity
--   from public.amenity_booking_occurrences o
--   join public.amenities am on am.id = o.amenity_id
--   join public.amenity_booking_occurrences x
--     on x.amenity_id = o.amenity_id and x.slot && o.slot
--    and not x.is_exclusive and x.status not in ('rejected','cancelled')
--   where not o.is_exclusive and o.status not in ('rejected','cancelled')
--     and am.capacity is not null
--   group by o.amenity_id, o.slot, am.capacity
--   having sum(x.occupant_count) > am.capacity;
--
-- Every amenity has exactly one settings row:
--   select a.id from public.amenities a
--   left join public.amenity_settings s on s.amenity_id = a.id
--   where s.amenity_id is null;
--
-- No booking belongs to an amenity in another community (the composite FKs
-- should make this impossible):
--   select o.id from public.amenity_booking_occurrences o
--   join public.amenities a on a.id = o.amenity_id
--   where a.community_id <> o.community_id;
--
-- No deposit has been refunded for more than was paid into it:
--   select c.id,
--          sum(e.amount) filter (where e.event_type = 'payment') as paid,
--          sum(e.amount) filter (where e.event_type in ('refund','damage_deduction'))
--            as taken
--   from public.amenity_booking_charges c
--   join public.amenity_financial_events e on e.booking_charge_id = c.id
--   where c.charge_type = 'deposit'
--   group by c.id
--   having coalesce(sum(e.amount) filter (where e.event_type in
--            ('refund','damage_deduction')), 0)
--        > coalesce(sum(e.amount) filter (where e.event_type = 'payment'), 0);
--
-- A blocked slot never carries a unit or a charge:
--   select b.id from public.amenity_booking_series b
--   where b.status = 'blocked' and b.unit_id is not null;
--
-- The ledger summary agrees with a direct sum over its own rows (expect one row
-- per amenity, each pair matching):
--   select s.amenity_id, s.total_revenue,
--          (select coalesce(sum(l.amount_paid), 0)
--             from public.amenity_ledger_overview l
--            where l.amenity_id = s.amenity_id)
--   from public.amenity_ledger_summary s;
