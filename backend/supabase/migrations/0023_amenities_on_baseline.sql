-- ===========================================================================
-- Step 8 rebuilt: amenities, bookings and the amenity ledger, on the baseline.
--
-- This replaces `legacy-preauth/0016_amenities.sql`, the largest of the
-- quarantined files and the only one that was a genuine design conflict rather
-- than a rename.
--
-- THE DESIGN CONFLICT, AND HOW IT IS SETTLED
--
-- 0016 modelled a booking as an `amenity_booking_series` plus one
-- `amenity_booking_occurrences` row per date. The baseline models it as a single
-- `amenity_bookings` table with a GIST exclusion constraint that makes
-- double-booking unrepresentable. The updated submission ERD (origin/main
-- @ db85c04) removed the series tables, siding with the baseline.
--
-- Conforming exactly would have cost a product behaviour. A resident books up to
-- thirty dates in one request (`ResidentBookingRequest.dates`), and an admin
-- approves the whole request with one click (`ApprovalRequest.dayCount`). One row
-- per date with nothing joining them would mean approving a twelve-date request
-- twelve times.
--
-- So: **the baseline's table stays the only booking table, and gains one
-- nullable `booking_group_id` column.** No series entity, no second table, the
-- ERD's table set unchanged, the exclusion constraint still doing its job per
-- row -- and a multi-date request is still one thing to approve. The name
-- converges with `bookingGroupId`, which their own `dashboard_service.py:149`
-- already emits.
--
-- A single-date booking gets a group of one. Nothing has to special-case it.
--
-- WHY THE MONEY LIVES IN ITS OWN LEDGER
--
-- The baseline has `booking_charges` and `booking_refunds`, which are enough to
-- record that a charge exists. The amenity ledger screen needs to answer "what
-- is outstanding on this booking, after deposits, refunds and damage" -- a
-- running balance across four kinds of movement. `amenity_financial_events` is
-- that append-only record; the baseline's two tables stay and are written
-- alongside it, so anything reading the baseline shape still sees its charges.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Amenity configuration
--
-- The baseline keeps booking policy in `amenities.booking_rules jsonb`. The
-- admin form has twenty-odd typed fields with their own validation, and a CHECK
-- constraint cannot see inside jsonb usefully. They become columns; the jsonb
-- column stays and is left alone, so their readers are unaffected.
-- ---------------------------------------------------------------------------
alter table public.amenities
  add column if not exists category                        text,
  add column if not exists location                        text,
  add column if not exists image_url                       text,
  add column if not exists capacity                        integer,
  add column if not exists booking_mode                    text not null default 'shared',
  add column if not exists approval_required                boolean not null default true,
  add column if not exists status                          text not null default 'active',
  add column if not exists version                         integer not null default 1,
  add column if not exists opening_time                    time,
  add column if not exists closing_time                    time,
  add column if not exists slot_duration_minutes           integer not null default 60,
  add column if not exists cleaning_buffer_minutes         integer not null default 0,
  add column if not exists max_active_bookings_per_resident integer,
  add column if not exists allow_private_booking           boolean not null default false,
  add column if not exists allow_recurring_booking         boolean not null default true,
  add column if not exists allow_guest_booking             boolean not null default true,
  add column if not exists allow_same_day_booking          boolean not null default true,
  add column if not exists enable_waitlist                 boolean not null default false,
  add column if not exists enable_auto_approval            boolean not null default false,
  add column if not exists booking_fee                     numeric(12, 2) not null default 0,
  add column if not exists security_deposit                numeric(12, 2) not null default 0,
  add column if not exists late_cancellation_charge        numeric(12, 2) not null default 0,
  add column if not exists damage_deposit                  numeric(12, 2) not null default 0,
  add column if not exists refund_policy                   text,
  add column if not exists currency_code                   char(3) not null default 'INR',
  add column if not exists closed_days                     jsonb not null default '[]'::jsonb,
  add column if not exists maintenance_days                jsonb not null default '[]'::jsonb,
  add column if not exists holiday_overrides               jsonb not null default '[]'::jsonb,
  -- The availability half of the settings form.
  add column if not exists temporary_closure                jsonb,
  add column if not exists minimum_booking_duration_minutes integer,
  add column if not exists maximum_booking_duration_minutes integer,
  add column if not exists advance_booking_window_days      integer,
  -- The maintenance half.
  add column if not exists maintenance_interval             text,
  add column if not exists default_maintenance_duration_minutes integer,
  add column if not exists auto_block_maintenance_slots     boolean not null default false,
  add column if not exists maintenance_notes                text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'amenities_booking_mode_check') then
    alter table public.amenities add constraint amenities_booking_mode_check
      check (booking_mode in ('shared', 'exclusive', 'hybrid'));
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenities_status_check') then
    alter table public.amenities add constraint amenities_status_check
      check (status in ('active', 'inactive', 'maintenance'));
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenities_amounts_check') then
    alter table public.amenities add constraint amenities_amounts_check
      check (booking_fee >= 0 and security_deposit >= 0
             and late_cancellation_charge >= 0 and damage_deposit >= 0);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenities_slot_check') then
    alter table public.amenities add constraint amenities_slot_check
      check (slot_duration_minutes between 5 and 1440
             and cleaning_buffer_minutes between 0 and 480);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenities_hours_check') then
    alter table public.amenities add constraint amenities_hours_check
      check (opening_time is null or closing_time is null or opening_time < closing_time);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenities_id_community_id_key') then
    alter table public.amenities add constraint amenities_id_community_id_key
      unique (id, community_id);
  end if;
end $$;

-- `status` and `is_active` say the same thing to two readers, as with
-- departments in 0019. 'maintenance' is not active.
create or replace function public.sync_amenity_status()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'INSERT' then
    if new.status is distinct from 'active' then
      new.is_active := (new.status = 'active');
    else
      new.status := case when new.is_active then 'active' else 'inactive' end;
    end if;
    return new;
  end if;

  if new.status is distinct from old.status then
    new.is_active := (new.status = 'active');
  elsif new.is_active is distinct from old.is_active then
    new.status := case when new.is_active then 'active' else 'inactive' end;
  end if;
  return new;
end $$;

drop trigger if exists amenities_sync_status on public.amenities;
create trigger amenities_sync_status
  before insert or update on public.amenities
  for each row execute function public.sync_amenity_status();

-- ---------------------------------------------------------------------------
-- 2. Bookings
--
-- `booking_group_id` is the whole of the series/occurrence reconciliation. It is
-- nullable so a booking made outside the multi-date flow needs nothing extra,
-- and it is NOT a foreign key to anything -- there is no group entity, only rows
-- that agree on an id.
--
-- `stored_status` is not a column. The view exposes the enum value under that
-- name beside the wire string, because the frontend compares against
-- 'Approved' while the database holds 'approved'.
-- ---------------------------------------------------------------------------
alter table public.amenity_bookings
  add column if not exists booking_group_id         uuid,
  add column if not exists unit_id                  uuid references public.units(id) on delete set null,
  add column if not exists title                    text,
  add column if not exists booking_type             text not null default 'resident',
  add column if not exists source                   text not null default 'resident',
  add column if not exists is_private               boolean not null default false,
  add column if not exists is_exclusive             boolean not null default false,
  add column if not exists guest_count              integer not null default 0,
  add column if not exists occupant_count           integer not null default 1,
  add column if not exists notes                    text,
  add column if not exists department               text,
  add column if not exists charge_override          numeric(12, 2),
  add column if not exists buffer_minutes           integer not null default 0,
  add column if not exists requested_at             timestamptz not null default now(),
  add column if not exists approved_at              timestamptz,
  add column if not exists rejected_at              timestamptz,
  add column if not exists rejection_reason         text,
  add column if not exists rejection_reason_code    text,
  add column if not exists cancelled_at             timestamptz,
  add column if not exists cancellation_reason      text,
  add column if not exists cancellation_reason_code text,
  add column if not exists cancelled_by_resident    boolean not null default false,
  add column if not exists force_cancelled          boolean not null default false;

alter table public.amenity_bookings alter column booked_by_membership_id drop not null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'amenity_bookings_type_check') then
    alter table public.amenity_bookings add constraint amenity_bookings_type_check
      check (booking_type in ('resident', 'admin', 'maintenance', 'blocked'));
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenity_bookings_counts_check') then
    alter table public.amenity_bookings add constraint amenity_bookings_counts_check
      check (guest_count >= 0 and occupant_count >= 0 and buffer_minutes >= 0);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'amenity_bookings_window_check') then
    alter table public.amenity_bookings add constraint amenity_bookings_window_check
      check (starts_at < ends_at);
  end if;

  -- A blocked slot has no resident behind it; anything else must have one.
  if not exists (select 1 from pg_constraint where conname = 'amenity_bookings_actor_check') then
    alter table public.amenity_bookings add constraint amenity_bookings_actor_check
      check (booking_type in ('maintenance', 'blocked')
             or booked_by_membership_id is not null);
  end if;
end $$;

create index if not exists amenity_bookings_group_idx
  on public.amenity_bookings (booking_group_id)
  where booking_group_id is not null;

create index if not exists amenity_bookings_community_date_idx
  on public.amenity_bookings (community_id, starts_at desc);

create index if not exists amenity_bookings_status_idx
  on public.amenity_bookings (amenity_id, status, starts_at);

-- ---------------------------------------------------------------------------
-- 3. Guests
--
-- Names and phone numbers typed into the booking form. No membership reference,
-- because a guest is by definition not a member.
-- ---------------------------------------------------------------------------
-- The column is `booking_series_id` rather than `booking_group_id` because that
-- is what `amenities_repository.list_guests` filters on, and the group id IS the
-- series id -- the two names describe the same uuid from either end. Renaming the
-- read side would have meant touching 3 900 lines of tested application code to
-- gain nothing.
create table if not exists public.amenity_booking_guests (
  id                uuid primary key default gen_random_uuid(),
  community_id      uuid not null references public.communities(id) on delete cascade,
  booking_series_id uuid not null,
  guest_name        text not null check (length(btrim(guest_name)) between 1 and 120),
  phone_e164        varchar(20),
  created_at        timestamptz not null default now()
);

create index if not exists amenity_booking_guests_group_idx
  on public.amenity_booking_guests (booking_series_id);

-- ---------------------------------------------------------------------------
-- 4. Charges and financial events
--
-- `amenity_booking_charges` is our per-booking breakdown; the baseline's
-- `booking_charges` is written alongside it by the RPCs so their shape stays
-- populated.
--
-- `amenity_financial_events` is append-only. A ledger that can be updated in
-- place cannot be audited, and this is the record of money taken from and
-- returned to residents.
-- ---------------------------------------------------------------------------
-- The hierarchy is booking -> charge -> event, which is what
-- `list_financial_events` walks: it reads the charges for a page of bookings,
-- then the events for those charges, and groups back up. Money moves against a
-- CHARGE, not against a booking -- a refund refunds a specific deposit, and a
-- ledger that recorded it against the booking could not say which.
create table if not exists public.amenity_booking_charges (
  id                    uuid primary key default gen_random_uuid(),
  community_id          uuid not null references public.communities(id) on delete cascade,
  booking_occurrence_id uuid not null references public.amenity_bookings(id) on delete cascade,
  charge_type           text not null check (charge_type in ('booking_fee', 'deposit', 'damage_deposit', 'late_cancellation', 'additional')),
  label                 text,
  amount                numeric(12, 2) not null check (amount >= 0),
  created_at            timestamptz not null default now()
);

create index if not exists amenity_booking_charges_booking_idx
  on public.amenity_booking_charges (booking_occurrence_id);

create table if not exists public.amenity_financial_events (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  booking_charge_id   uuid not null references public.amenity_booking_charges(id) on delete cascade,
  event_type          text not null check (event_type in ('payment', 'refund', 'damage_deduction', 'charge')),
  amount              numeric(12, 2) not null check (amount >= 0),
  payment_reference   text,
  reason              text,
  notes               text,
  actor_membership_id uuid references public.community_memberships(id) on delete set null,
  created_at          timestamptz not null default now()
);

create index if not exists amenity_financial_events_charge_idx
  on public.amenity_financial_events (booking_charge_id, created_at);

-- Idempotency for payments, matching what `payments` gets in 0021: a repeated
-- reference is the same payment, not a second one.
create unique index if not exists amenity_financial_events_reference_key
  on public.amenity_financial_events (community_id, event_type, payment_reference)
  where payment_reference is not null;

-- ---------------------------------------------------------------------------
-- 5. amenity_overview
-- ---------------------------------------------------------------------------
drop view if exists public.amenity_overview;
create view public.amenity_overview
with (security_invoker = true) as
select
  a.id, a.community_id, a.name, a.description, a.category, a.location,
  a.image_url, a.capacity, a.booking_mode, a.approval_required, a.status,
  a.is_active, a.version, a.created_at, a.updated_at,
  a.opening_time, a.closing_time, a.slot_duration_minutes,
  a.cleaning_buffer_minutes, a.max_active_bookings_per_resident,
  a.allow_private_booking, a.allow_recurring_booking, a.allow_guest_booking,
  a.allow_same_day_booking, a.enable_waitlist, a.enable_auto_approval,
  a.booking_fee, a.security_deposit, a.late_cancellation_charge,
  a.damage_deposit, a.refund_policy, a.currency_code,
  a.closed_days, a.maintenance_days, a.holiday_overrides,
  a.temporary_closure, a.minimum_booking_duration_minutes,
  a.maximum_booking_duration_minutes, a.advance_booking_window_days,
  a.maintenance_interval, a.default_maintenance_duration_minutes,
  a.auto_block_maintenance_slots, a.maintenance_notes,
  coalesce(b.upcoming_booking_count, 0) as upcoming_booking_count,
  coalesce(b.pending_booking_count, 0)  as pending_booking_count,
  coalesce(b.pending_booking_count, 0)  as pending_requests,
  -- What this amenity is still owed, across every booking against it. Computed
  -- from the ledger rather than stored, for the reason in `money_schemas.py`.
  coalesce(d.outstanding_dues, 0)       as outstanding_dues,
  lower(concat_ws(' ', a.name, a.description, a.category, a.location)) as search_text
from public.amenities a
left join lateral (
  select
    count(*) filter (where bk.starts_at >= now() and bk.status = 'approved')  as upcoming_booking_count,
    count(*) filter (where bk.status = 'requested')                           as pending_booking_count
    from public.amenity_bookings bk
   where bk.amenity_id = a.id
) b on true
left join lateral (
  -- Charges raised against this amenity's bookings, less what has been paid.
  -- Computed from the base tables rather than from `amenity_ledger_overview`,
  -- which is defined further down: a view cannot reference one that does not
  -- exist yet, and reordering the file to suit would put the ledger before the
  -- amenity it belongs to.
  select greatest(coalesce(ch.raised, 0) - coalesce(pd.paid, 0), 0) as outstanding_dues
    from (
      select sum(x.amount) as raised
        from public.amenity_booking_charges x
        join public.amenity_bookings bx on bx.id = x.booking_occurrence_id
       where bx.amenity_id = a.id
    ) ch
    cross join (
      select sum(e.amount) as paid
        from public.amenity_financial_events e
        join public.amenity_booking_charges xc on xc.id = e.booking_charge_id
        join public.amenity_bookings bx on bx.id = xc.booking_occurrence_id
       where bx.amenity_id = a.id
         and e.event_type = 'payment'
    ) pd
) d on true;

comment on view public.amenity_overview is
  'Amenities with their booking policy and pending/upcoming counts.';

-- ---------------------------------------------------------------------------
-- 6. amenity_booking_overview
--
-- `status` is the wire string the frontend compares against; `stored_status` is
-- the enum underneath. Both are exposed so no caller has to map between them.
--
-- `series_status` is the status of the GROUP: a multi-date request is pending
-- while any date is pending, approved once every remaining date is approved.
-- That is what the approvals queue shows on one row.
-- ---------------------------------------------------------------------------
drop view if exists public.amenity_booking_overview;
create view public.amenity_booking_overview
with (security_invoker = true) as
select
  bk.id,
  bk.community_id,
  coalesce(bk.booking_group_id, bk.id) as booking_series_id,
  bk.amenity_id,
  am.name                              as amenity_name,
  am.booking_mode,
  (bk.starts_at at time zone coalesce(cs.timezone, c.timezone, 'Asia/Kolkata'))::date as booking_date,
  bk.starts_at,
  bk.ends_at,
  bk.is_exclusive,
  bk.buffer_minutes,
  bk.occupant_count,
  case bk.status
    when 'requested' then 'Pending'
    when 'approved'  then 'Approved'
    when 'rejected'  then 'Rejected'
    when 'cancelled' then 'Cancelled'
    when 'completed' then 'Completed'
    when 'no_show'   then 'No Show'
    else initcap(bk.status::text)
  end                                  as status,
  bk.status::text                      as stored_status,
  bk.cancelled_at,
  bk.cancellation_reason_code,
  bk.cancellation_reason,
  bk.cancelled_by_resident,
  bk.force_cancelled,
  bk.aggregate_version                 as version,
  bk.created_at,
  bk.updated_at,
  bk.title,
  bk.booking_type,
  bk.source,
  bk.is_private,
  am.approval_required                 as requires_approval,
  bk.guest_count,
  bk.notes,
  bk.charge_override,
  bk.department,
  grp.series_status,
  -- How many dates this request covers. The approvals queue shows one row per
  -- request and needs to say "3 days" beside it, which is a count over the
  -- group rather than anything on this row.
  grp.day_count,
  bk.requested_at,
  bk.approved_at,
  bk.rejected_at,
  bk.rejection_reason,
  bk.rejection_reason_code,
  bk.unit_id,
  u.unit_code,
  bldg.name                            as tower,
  bk.booked_by_membership_id           as requested_by_membership_id,
  m.profile_id                         as resident_profile_id,
  pr.full_name                         as resident_name,
  lower(concat_ws(' ', am.name, bk.title, u.unit_code, pr.full_name)) as search_text
from public.amenity_bookings bk
join public.amenities am               on am.id = bk.amenity_id
join public.communities c              on c.id = bk.community_id
left join public.community_settings cs on cs.community_id = bk.community_id
left join public.units u               on u.id = bk.unit_id
left join public.buildings bldg        on bldg.id = u.building_id
left join public.community_memberships m on m.id = bk.booked_by_membership_id
left join public.profiles pr           on pr.id = m.profile_id
left join lateral (
  select case
           when count(*) filter (where g.status = 'requested') > 0 then 'pending'
           when count(*) filter (where g.status = 'approved')  > 0 then 'approved'
           when count(*) filter (where g.status = 'rejected')  > 0 then 'rejected'
           else 'cancelled'
         end as series_status,
         count(*) as day_count
    from public.amenity_bookings g
   where coalesce(g.booking_group_id, g.id) = coalesce(bk.booking_group_id, bk.id)
) grp on true;

comment on view public.amenity_booking_overview is
  'Bookings with the amenity, flat, resident and the status of their whole group. booking_series_id is the group id, falling back to the row id.';

-- ---------------------------------------------------------------------------
-- 7. amenity_ledger_overview
--
-- Every figure is an aggregate over `amenity_financial_events`, computed in
-- numeric by Postgres. Nothing here is summed by the caller, for the reason
-- given in `money_schemas.py`.
-- ---------------------------------------------------------------------------
drop view if exists public.amenity_ledger_overview;
create view public.amenity_ledger_overview
with (security_invoker = true) as
select
  bk.id                                as id,
  bk.community_id,
  bk.id                                as booking_id,
  coalesce(bk.booking_group_id, bk.id) as booking_series_id,
  bk.amenity_id,
  am.name                              as amenity_name,
  bk.unit_id,
  u.unit_code,
  m.profile_id                         as resident_profile_id,
  pr.full_name                         as resident_name,
  bk.booked_by_membership_id           as requested_by_membership_id,
  (bk.starts_at at time zone coalesce(c.timezone, 'Asia/Kolkata'))::date as booking_date,
  bk.starts_at,
  bk.ends_at,
  bk.booking_type,
  bk.title,
  bk.notes,
  bk.status::text                      as booking_status,
  bk.force_cancelled,
  bk.cancelled_at,
  bk.cancellation_reason,
  bk.approved_at,
  bk.created_at,
  bk.updated_at,
  ev.payment_reference,
  coalesce(ch.deposit_amount, 0)       as deposit_amount,
  (coalesce(ev.amount_paid, 0) >= coalesce(ch.deposit_amount, 0)
   and coalesce(ch.deposit_amount, 0) > 0) as deposit_paid,
  coalesce(ch.booking_charges, 0)      as booking_charges,
  coalesce(ch.additional_charges, 0)   as additional_charges,
  coalesce(ev.amount_paid, 0)          as amount_paid,
  coalesce(ev.refund_amount, 0)        as refund_amount,
  coalesce(ev.damage_amount, 0)        as damage_amount,
  coalesce(ch.total_amount, 0)         as total_amount,
  greatest(coalesce(ch.deposit_amount, 0) - coalesce(ev.amount_paid, 0), 0) as outstanding_deposit,
  greatest(
    coalesce(ev.amount_paid, 0)
      - coalesce(ev.refund_amount, 0)
      - coalesce(ev.damage_amount, 0)
      - coalesce(ch.non_refundable, 0),
    0
  )                                    as remaining_refund,
  case
    when coalesce(ch.total_amount, 0) = 0                              then 'not_applicable'
    when coalesce(ev.amount_paid, 0) >= coalesce(ch.total_amount, 0)   then 'paid'
    when coalesce(ev.amount_paid, 0) > 0                               then 'partial'
    else 'unpaid'
  end                                  as payment_status
from public.amenity_bookings bk
join public.amenities am                 on am.id = bk.amenity_id
join public.communities c                on c.id = bk.community_id
left join public.units u                 on u.id = bk.unit_id
left join public.community_memberships m on m.id = bk.booked_by_membership_id
left join public.profiles pr             on pr.id = m.profile_id
left join lateral (
  select
    sum(x.amount)                                                              as total_amount,
    sum(x.amount) filter (where x.charge_type in ('deposit', 'damage_deposit')) as deposit_amount,
    sum(x.amount) filter (where x.charge_type = 'booking_fee')                 as booking_charges,
    sum(x.amount) filter (where x.charge_type = 'additional')                  as additional_charges,
    sum(x.amount) filter (where x.charge_type in ('booking_fee', 'late_cancellation', 'additional')) as non_refundable
    from public.amenity_booking_charges x
   where x.booking_occurrence_id = bk.id
) ch on true
left join lateral (
  select
    sum(e.amount) filter (where e.event_type = 'payment')          as amount_paid,
    sum(e.amount) filter (where e.event_type = 'refund')           as refund_amount,
    sum(e.amount) filter (where e.event_type = 'damage_deduction') as damage_amount,
    (array_agg(e.payment_reference order by e.created_at desc)
       filter (where e.event_type = 'payment' and e.payment_reference is not null))[1] as payment_reference
    from public.amenity_financial_events e
    join public.amenity_booking_charges xc on xc.id = e.booking_charge_id
   where xc.booking_occurrence_id = bk.id
) ev on true;

comment on view public.amenity_ledger_overview is
  'Per-booking money: charges raised, paid, refunded and deducted, with the resulting balance.';

-- ---------------------------------------------------------------------------
-- 8. amenity_ledger_summary
--
-- The KPI row above the ledger table. Grouped by amenity as well as community,
-- because `fetch_ledger_summary` filters on both -- the ledger tab is per
-- amenity, not community-wide.
--
-- `refund_pending` and `refund_completed` split the same money by whether it has
-- gone back yet, which is the distinction the tab's two counters draw.
-- ---------------------------------------------------------------------------
drop view if exists public.amenity_ledger_summary;
create view public.amenity_ledger_summary
with (security_invoker = true) as
select
  l.community_id,
  l.amenity_id,
  count(*)                                              as total_bookings,
  coalesce(sum(l.amount_paid), 0)                       as total_revenue,
  coalesce(sum(l.outstanding_deposit), 0)               as pending_deposits,
  coalesce(sum(l.remaining_refund), 0)                  as refund_pending,
  coalesce(sum(l.refund_amount), 0)                     as refund_completed,
  coalesce(sum(l.damage_amount), 0)                     as damage_deductions,
  coalesce(sum(l.remaining_refund), 0)                  as outstanding_refunds,
  count(*) filter (where l.payment_status = 'paid')     as completed_transactions
from public.amenity_ledger_overview l
group by l.community_id, l.amenity_id;

comment on view public.amenity_ledger_summary is
  'Per-amenity totals for the ledger KPI row.';

grant select on public.amenity_overview          to authenticated;
grant select on public.amenity_booking_overview  to authenticated;
grant select on public.amenity_ledger_overview   to authenticated;
grant select on public.amenity_ledger_summary    to authenticated;

-- ---------------------------------------------------------------------------
-- 9. Helpers
-- ---------------------------------------------------------------------------

-- Raise the charges an amenity's policy implies for one booking. Called once,
-- when the booking row is created; a later change to the amenity's fees does not
-- retroactively re-price a booking somebody already made.
create or replace function public.raise_amenity_charges(p_booking_id uuid)
returns void
language plpgsql
as $$
declare
  v_b public.amenity_bookings%rowtype;
  v_a public.amenities%rowtype;
begin
  select * into v_b from public.amenity_bookings where id = p_booking_id;
  select * into v_a from public.amenities where id = v_b.amenity_id;

  if v_b.booking_type in ('maintenance', 'blocked') then
    return;
  end if;

  -- An explicit override replaces the fee, not the deposits.
  if coalesce(v_b.charge_override, v_a.booking_fee) > 0 then
    insert into public.amenity_booking_charges
      (community_id, booking_occurrence_id, charge_type, label, amount)
    values (v_b.community_id, p_booking_id, 'booking_fee', 'Booking fee',
            coalesce(v_b.charge_override, v_a.booking_fee));
  end if;

  if v_a.security_deposit > 0 then
    insert into public.amenity_booking_charges
      (community_id, booking_occurrence_id, charge_type, label, amount)
    values (v_b.community_id, p_booking_id, 'deposit', 'Security deposit', v_a.security_deposit);
  end if;

  if v_a.damage_deposit > 0 then
    insert into public.amenity_booking_charges
      (community_id, booking_occurrence_id, charge_type, label, amount)
    values (v_b.community_id, p_booking_id, 'damage_deposit', 'Damage deposit', v_a.damage_deposit);
  end if;

  -- Mirror the total into the baseline's own table so its readers see it.
  insert into public.booking_charges (booking_id, amount, kind, status)
  select p_booking_id, coalesce(sum(amount), 0), 'amenity', 'pending'
    from public.amenity_booking_charges where booking_occurrence_id = p_booking_id
  having coalesce(sum(amount), 0) > 0;
end $$;

-- Resolve the charge a movement should hang off. Money moves against a specific
-- charge, but the endpoints are addressed by BOOKING -- the ledger screen offers
-- "refund this booking's deposit", not "refund charge 7fa3". This picks the one
-- the movement obviously means, and creates a catch-all charge when a booking
-- has none, so a payment against a free booking is still recordable.
create or replace function public.amenity_charge_for(
  p_booking_id uuid,
  p_prefer     text
)
returns uuid
language plpgsql
as $$
declare
  v_id           uuid;
  v_community_id uuid;
begin
  select id into v_id
    from public.amenity_booking_charges
   where booking_occurrence_id = p_booking_id
     and charge_type = p_prefer
   order by created_at
   limit 1;

  if v_id is not null then
    return v_id;
  end if;

  select id into v_id
    from public.amenity_booking_charges
   where booking_occurrence_id = p_booking_id
   order by created_at
   limit 1;

  if v_id is not null then
    return v_id;
  end if;

  select community_id into v_community_id
    from public.amenity_bookings where id = p_booking_id;

  insert into public.amenity_booking_charges
    (community_id, booking_occurrence_id, charge_type, label, amount)
  values (v_community_id, p_booking_id, 'additional', 'Adjustment', 0)
  returning id into v_id;

  return v_id;
end $$;

revoke all on function public.amenity_charge_for(uuid, text) from public, anon, authenticated;

revoke all on function public.raise_amenity_charges(uuid) from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- 10. Amenity configuration RPCs
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
  v_id uuid := p_amenity_id;
  v_s  jsonb := coalesce(p_payload -> 'settings', '{}'::jsonb);
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may change an amenity.'
      using errcode = '42501';
  end if;

  if v_id is null then
    insert into public.amenities (community_id, name)
    values (p_community_id, btrim(coalesce(p_payload ->> 'name', 'Amenity')))
    returning id into v_id;
  else
    if not exists (
      select 1 from public.amenities where id = v_id and community_id = p_community_id
    ) then
      raise exception 'Amenity not found.' using errcode = 'P0002';
    end if;
  end if;

  update public.amenities
     set name              = case when p_payload ? 'name'              then btrim(p_payload ->> 'name') else name end,
         description       = case when p_payload ? 'description'       then nullif(btrim(coalesce(p_payload ->> 'description', '')), '') else description end,
         category          = case when p_payload ? 'category'          then nullif(btrim(coalesce(p_payload ->> 'category', '')), '') else category end,
         location          = case when p_payload ? 'location'          then nullif(btrim(coalesce(p_payload ->> 'location', '')), '') else location end,
         image_url         = case when p_payload ? 'image_url'         then nullif(btrim(coalesce(p_payload ->> 'image_url', '')), '') else image_url end,
         capacity          = case when p_payload ? 'capacity'          then (nullif(p_payload ->> 'capacity', ''))::integer else capacity end,
         booking_mode      = case when p_payload ? 'booking_mode'      then p_payload ->> 'booking_mode' else booking_mode end,
         approval_required = case when p_payload ? 'approval_required' then (p_payload ->> 'approval_required')::boolean else approval_required end,
         status            = case when p_payload ? 'is_active'
                                  then case when (p_payload ->> 'is_active')::boolean then 'active' else 'inactive' end
                                  else status end,
         closed_days       = case when p_payload ? 'closed_days'       then p_payload -> 'closed_days' else closed_days end,
         maintenance_days  = case when p_payload ? 'maintenance_days'  then p_payload -> 'maintenance_days' else maintenance_days end,
         holiday_overrides = case when p_payload ? 'holiday_overrides' then p_payload -> 'holiday_overrides' else holiday_overrides end,

         opening_time                     = case when v_s ? 'opening_time'                     then (nullif(v_s ->> 'opening_time', ''))::time else opening_time end,
         closing_time                     = case when v_s ? 'closing_time'                     then (nullif(v_s ->> 'closing_time', ''))::time else closing_time end,
         slot_duration_minutes            = case when v_s ? 'slot_duration_minutes'            then (v_s ->> 'slot_duration_minutes')::integer else slot_duration_minutes end,
         cleaning_buffer_minutes          = case when v_s ? 'cleaning_buffer_minutes'          then (v_s ->> 'cleaning_buffer_minutes')::integer else cleaning_buffer_minutes end,
         max_active_bookings_per_resident = case when v_s ? 'max_active_bookings_per_resident' then (nullif(v_s ->> 'max_active_bookings_per_resident', ''))::integer else max_active_bookings_per_resident end,
         allow_private_booking            = case when v_s ? 'allow_private_booking'            then (v_s ->> 'allow_private_booking')::boolean else allow_private_booking end,
         allow_recurring_booking          = case when v_s ? 'allow_recurring_booking'          then (v_s ->> 'allow_recurring_booking')::boolean else allow_recurring_booking end,
         allow_guest_booking              = case when v_s ? 'allow_guest_booking'              then (v_s ->> 'allow_guest_booking')::boolean else allow_guest_booking end,
         allow_same_day_booking           = case when v_s ? 'allow_same_day_booking'           then (v_s ->> 'allow_same_day_booking')::boolean else allow_same_day_booking end,
         enable_waitlist                  = case when v_s ? 'enable_waitlist'                  then (v_s ->> 'enable_waitlist')::boolean else enable_waitlist end,
         enable_auto_approval             = case when v_s ? 'enable_auto_approval'             then (v_s ->> 'enable_auto_approval')::boolean else enable_auto_approval end,
         booking_fee                      = case when v_s ? 'booking_fee'                      then (v_s ->> 'booking_fee')::numeric else booking_fee end,
         security_deposit                 = case when v_s ? 'security_deposit'                 then (v_s ->> 'security_deposit')::numeric else security_deposit end,
         late_cancellation_charge         = case when v_s ? 'late_cancellation_charge'         then (v_s ->> 'late_cancellation_charge')::numeric else late_cancellation_charge end,
         damage_deposit                   = case when v_s ? 'damage_deposit'                   then (v_s ->> 'damage_deposit')::numeric else damage_deposit end,
         refund_policy                    = case when v_s ? 'refund_policy'                    then nullif(btrim(coalesce(v_s ->> 'refund_policy', '')), '') else refund_policy end,

         version    = version + 1,
         updated_at = now()
   where id = v_id;

  return v_id;
end $$;

-- Refuses while future bookings exist. Deleting the amenity would cascade them
-- away, silently cancelling bookings residents are relying on.
create or replace function public.delete_amenity(p_amenity_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_future       integer;
begin
  select community_id into v_community_id from public.amenities where id = p_amenity_id;

  if v_community_id is null then
    raise exception 'Amenity not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may delete an amenity.'
      using errcode = '42501';
  end if;

  select count(*) into v_future
    from public.amenity_bookings
   where amenity_id = p_amenity_id
     and starts_at >= now()
     and status in ('requested', 'approved');

  if v_future > 0 then
    raise exception 'This amenity has % upcoming booking(s).', v_future
      using errcode = '23503';
  end if;

  delete from public.amenities where id = p_amenity_id;
end $$;

-- ---------------------------------------------------------------------------
-- 11. Booking creation
--
-- All three creators share one shape: expand the requested dates into one row
-- per date, all carrying the same `booking_group_id`, then raise the charges.
--
-- The GIST exclusion constraint on `amenity_bookings` does the conflict
-- detection. A clash raises `23P01`, which `pg_errors.translate` turns into a
-- 409 -- so double-booking is refused by the database rather than by a check
-- that races.
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
  v_community_id uuid;
  v_group_id     uuid := gen_random_uuid();
  v_membership   uuid;
  v_unit         uuid;
  v_date         text;
  v_starts       time := (nullif(p_payload ->> 'starts_at', ''))::time;
  v_ends         time := (nullif(p_payload ->> 'ends_at', ''))::time;
  v_tz           text;
  v_booking_id   uuid;
  v_guest        jsonb;
  v_auto         boolean;
begin
  select community_id into v_community_id from public.amenities where id = p_amenity_id;
  if v_community_id is null then
    raise exception 'Amenity not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_member(v_community_id) then
    raise exception 'Only a member of this community may book.' using errcode = '42501';
  end if;

  select m.id into v_membership
    from public.community_memberships m
   where m.community_id = v_community_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
   limit 1;

  select r.unit_id into v_unit
    from public.unit_residencies r
   where r.membership_id = v_membership and r.ended_at is null
   order by r.is_primary_contact desc
   limit 1;

  select coalesce(cs.timezone, c.timezone, 'Asia/Kolkata') into v_tz
    from public.communities c
    left join public.community_settings cs on cs.community_id = c.id
   where c.id = v_community_id;

  select enable_auto_approval or not approval_required into v_auto
    from public.amenities where id = p_amenity_id;

  for v_date in select jsonb_array_elements_text(p_payload -> 'dates') loop
    insert into public.amenity_bookings (
      amenity_id, community_id, booked_by_membership_id, booking_group_id,
      unit_id, starts_at, ends_at, status, title, booking_type, source,
      is_private, guest_count, notes
    )
    values (
      p_amenity_id, v_community_id, v_membership, v_group_id, v_unit,
      (v_date::date + v_starts) at time zone v_tz,
      (v_date::date + v_ends)   at time zone v_tz,
      case when v_auto then 'approved'::public.booking_status
           else 'requested'::public.booking_status end,
      nullif(btrim(coalesce(p_payload ->> 'title', '')), ''),
      'resident', 'resident',
      coalesce((p_payload ->> 'is_private')::boolean, false),
      coalesce((p_payload ->> 'guest_count')::integer, 0),
      nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
    )
    returning id into v_booking_id;

    perform public.raise_amenity_charges(v_booking_id);
  end loop;

  if p_payload ? 'guests' then
    for v_guest in select * from jsonb_array_elements(p_payload -> 'guests') loop
      insert into public.amenity_booking_guests
        (community_id, booking_series_id, guest_name, phone_e164)
      values (
        v_community_id, v_group_id,
        btrim(coalesce(v_guest ->> 'name', '')),
        nullif(btrim(coalesce(v_guest ->> 'phone', '')), '')
      );
    end loop;
  end if;

  return v_group_id;
end $$;

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
  v_community_id uuid;
  v_group_id     uuid := gen_random_uuid();
  v_membership   uuid := nullif(p_payload ->> 'membership_id', '')::uuid;
  v_unit         uuid;
  v_tz           text;
  v_booking_id   uuid;
  v_guest        jsonb;
begin
  select community_id into v_community_id from public.amenities where id = p_amenity_id;
  if v_community_id is null then
    raise exception 'Amenity not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may book on behalf of a resident.'
      using errcode = '42501';
  end if;

  select coalesce(cs.timezone, c.timezone, 'Asia/Kolkata') into v_tz
    from public.communities c
    left join public.community_settings cs on cs.community_id = c.id
   where c.id = v_community_id;

  select r.unit_id into v_unit
    from public.unit_residencies r
   where r.membership_id = v_membership and r.ended_at is null
   limit 1;

  insert into public.amenity_bookings (
    amenity_id, community_id, booked_by_membership_id, booking_group_id, unit_id,
    starts_at, ends_at, status, title, booking_type, source, is_private,
    guest_count, notes, charge_override, approved_at
  )
  values (
    p_amenity_id, v_community_id, v_membership, v_group_id, v_unit,
    ((p_payload ->> 'booking_date')::date + (p_payload ->> 'starts_at')::time) at time zone v_tz,
    ((p_payload ->> 'booking_date')::date + (p_payload ->> 'ends_at')::time)   at time zone v_tz,
    'approved',
    nullif(btrim(coalesce(p_payload ->> 'title', '')), ''),
    coalesce(nullif(p_payload ->> 'booking_type', ''), 'admin'),
    'admin',
    coalesce((p_payload ->> 'is_private')::boolean, false),
    coalesce((p_payload ->> 'guest_count')::integer, 0),
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), ''),
    (nullif(p_payload ->> 'charge_override', ''))::numeric,
    now()
  )
  returning id into v_booking_id;

  perform public.raise_amenity_charges(v_booking_id);

  if p_payload ? 'guests' then
    for v_guest in select * from jsonb_array_elements(p_payload -> 'guests') loop
      insert into public.amenity_booking_guests
        (community_id, booking_series_id, guest_name, phone_e164)
      values (v_community_id, v_group_id,
              btrim(coalesce(v_guest ->> 'name', '')),
              nullif(btrim(coalesce(v_guest ->> 'phone', '')), ''));
    end loop;
  end if;

  return v_group_id;
end $$;

-- A maintenance block is a booking with no resident behind it. Modelling it as
-- one means the exclusion constraint stops residents booking over it for free,
-- rather than needing a second overlap check against a separate table.
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
  v_community_id uuid;
  v_group_id     uuid := gen_random_uuid();
  v_tz           text;
  v_booking_id   uuid;
begin
  select community_id into v_community_id from public.amenities where id = p_amenity_id;
  if v_community_id is null then
    raise exception 'Amenity not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may block a slot.'
      using errcode = '42501';
  end if;

  select coalesce(cs.timezone, c.timezone, 'Asia/Kolkata') into v_tz
    from public.communities c
    left join public.community_settings cs on cs.community_id = c.id
   where c.id = v_community_id;

  insert into public.amenity_bookings (
    amenity_id, community_id, booking_group_id, starts_at, ends_at, status,
    title, booking_type, source, department, notes, approved_at
  )
  values (
    p_amenity_id, v_community_id, v_group_id,
    ((p_payload ->> 'booking_date')::date + (p_payload ->> 'starts_at')::time) at time zone v_tz,
    ((p_payload ->> 'booking_date')::date + (p_payload ->> 'ends_at')::time)   at time zone v_tz,
    'approved', btrim(coalesce(p_payload ->> 'reason', 'Blocked')),
    'blocked', 'admin',
    nullif(btrim(coalesce(p_payload ->> 'department', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), ''),
    now()
  )
  returning id into v_booking_id;

  -- Mirror into the baseline's own maintenance-block table, so anything reading
  -- that shape sees the closure too.
  insert into public.amenity_maintenance_blocks (amenity_id, starts_at, ends_at, reason)
  select amenity_id, starts_at, ends_at, title
    from public.amenity_bookings where id = v_booking_id;

  return v_group_id;
end $$;

-- ---------------------------------------------------------------------------
-- 12. Approval, rejection and cancellation
--
-- All four act on the GROUP, which is the behaviour the approvals queue needs:
-- one click decides a multi-date request.
-- ---------------------------------------------------------------------------
create or replace function public.approve_amenity_booking(p_series_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings
   where coalesce(booking_group_id, id) = p_series_id
   limit 1;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may approve a booking.'
      using errcode = '42501';
  end if;

  update public.amenity_bookings
     set status = 'approved', approved_at = now(),
         aggregate_version = aggregate_version + 1, updated_at = now()
   where coalesce(booking_group_id, id) = p_series_id
     and status = 'requested';
end $$;

create or replace function public.reject_amenity_booking(p_series_id uuid, p_payload jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings
   where coalesce(booking_group_id, id) = p_series_id
   limit 1;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may reject a booking.'
      using errcode = '42501';
  end if;

  update public.amenity_bookings
     set status = 'rejected', rejected_at = now(),
         rejection_reason      = nullif(btrim(coalesce(p_payload ->> 'reason', '')), ''),
         rejection_reason_code = nullif(btrim(coalesce(p_payload ->> 'reason_code', '')), ''),
         aggregate_version = aggregate_version + 1, updated_at = now()
   where coalesce(booking_group_id, id) = p_series_id
     and status = 'requested';
end $$;

-- Cancels a named set of dates rather than a whole group: a resident dropping
-- one Sunday out of eight is the common case.
create or replace function public.cancel_amenity_occurrences(p_payload jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ids          uuid[];
  v_community_id uuid;
  v_is_admin     boolean;
begin
  select array(select jsonb_array_elements_text(p_payload -> 'occurrence_ids')::uuid)
    into v_ids;

  if v_ids is null or array_length(v_ids, 1) is null then
    return;
  end if;

  select community_id into v_community_id
    from public.amenity_bookings where id = v_ids[1];

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  v_is_admin := public.is_community_admin(v_community_id);

  if not v_is_admin and not public.is_community_member(v_community_id) then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  update public.amenity_bookings b
     set status = 'cancelled',
         cancelled_at = now(),
         cancellation_reason      = nullif(btrim(coalesce(p_payload ->> 'reason', '')), ''),
         cancellation_reason_code = nullif(btrim(coalesce(p_payload ->> 'reason_code', '')), ''),
         cancelled_by_resident    = not v_is_admin,
         aggregate_version = aggregate_version + 1,
         updated_at = now()
   where b.id = any(v_ids)
     and b.status in ('requested', 'approved')
     -- A resident may only cancel their own.
     and (v_is_admin or exists (
       select 1 from public.community_memberships m
        where m.id = b.booked_by_membership_id and m.profile_id = auth.uid()
     ));
end $$;

-- The admin override: cancels regardless of who owns it or how late it is, and
-- says so on the row, because a forced cancellation is the kind of thing that
-- gets questioned later.
create or replace function public.force_cancel_amenity_booking(
  p_occurrence_id uuid,
  p_payload       jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings where id = p_occurrence_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may force-cancel a booking.'
      using errcode = '42501';
  end if;

  update public.amenity_bookings
     set status = 'cancelled',
         cancelled_at = now(),
         force_cancelled = true,
         cancellation_reason      = nullif(btrim(coalesce(p_payload ->> 'reason', '')), ''),
         cancellation_reason_code = nullif(btrim(coalesce(p_payload ->> 'reason_code', '')), ''),
         aggregate_version = aggregate_version + 1,
         updated_at = now()
   where id = p_occurrence_id;
end $$;

-- ---------------------------------------------------------------------------
-- 13. Ledger movements
--
-- Four RPCs, one shape: append an event, never update one. `record_amenity_payment`
-- is idempotent on its reference, enforced by the partial unique index above
-- rather than by a check that races.
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
  v_community_id uuid;
  v_reference    text := nullif(btrim(coalesce(p_payload ->> 'reference', '')), '');
  v_id           uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings where id = p_occurrence_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may record a payment.'
      using errcode = '42501';
  end if;

  if v_reference is not null then
    select id into v_id
      from public.amenity_financial_events
     where community_id = v_community_id
       and event_type = 'payment'
       and payment_reference = v_reference
     limit 1;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.amenity_financial_events
    (community_id, booking_charge_id, event_type, amount, payment_reference, notes)
  values (
    v_community_id,
    public.amenity_charge_for(p_occurrence_id, 'deposit'),
    'payment',
    (p_payload ->> 'amount')::numeric, v_reference,
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
  )
  returning id into v_id;

  return v_id;
end $$;

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
  v_community_id uuid;
  v_available    numeric(12, 2);
  v_amount       numeric(12, 2) := (p_payload ->> 'amount')::numeric;
  v_id           uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings where id = p_occurrence_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may issue a refund.'
      using errcode = '42501';
  end if;

  -- Refusing to refund more than was taken is the whole point of computing the
  -- balance in the database rather than trusting a number off the screen.
  select remaining_refund into v_available
    from public.amenity_ledger_overview where booking_id = p_occurrence_id;

  if v_amount > coalesce(v_available, 0) then
    raise exception 'Refund of % exceeds the % available.', v_amount, coalesce(v_available, 0)
      using errcode = '23514';
  end if;

  insert into public.amenity_financial_events
    (community_id, booking_charge_id, event_type, amount, payment_reference, reason, notes)
  values (
    v_community_id,
    public.amenity_charge_for(p_occurrence_id, 'deposit'),
    'refund', v_amount,
    nullif(btrim(coalesce(p_payload ->> 'reference', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'reason', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
  )
  returning id into v_id;

  insert into public.booking_refunds (booking_charge_id, amount, reason)
  select bc.id, v_amount, nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
    from public.booking_charges bc
   where bc.booking_id = p_occurrence_id
   limit 1;

  return v_id;
end $$;

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
  v_community_id uuid;
  v_id           uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings where id = p_occurrence_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may record damage.'
      using errcode = '42501';
  end if;

  insert into public.amenity_financial_events
    (community_id, booking_charge_id, event_type, amount, reason, notes)
  values (
    v_community_id,
    public.amenity_charge_for(p_occurrence_id, 'damage_deposit'),
    'damage_deduction',
    (p_payload ->> 'amount')::numeric,
    nullif(btrim(coalesce(p_payload ->> 'reason', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
  )
  returning id into v_id;

  return v_id;
end $$;

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
  v_community_id uuid;
  v_id           uuid;
begin
  select community_id into v_community_id
    from public.amenity_bookings where id = p_occurrence_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may add a charge.'
      using errcode = '42501';
  end if;

  insert into public.amenity_booking_charges
    (community_id, booking_occurrence_id, charge_type, label, amount)
  values (
    v_community_id, p_occurrence_id, 'additional',
    nullif(btrim(coalesce(p_payload ->> 'label', '')), ''),
    (p_payload ->> 'amount')::numeric
  )
  returning id into v_id;

  insert into public.amenity_financial_events
    (community_id, booking_charge_id, event_type, amount, notes)
  values (
    v_community_id, v_id, 'charge',
    (p_payload ->> 'amount')::numeric,
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), '')
  );

  return v_id;
end $$;

-- ---------------------------------------------------------------------------
-- 14. amenity_report_totals
--
-- Returns the report as one jsonb document rather than a rowset, because the
-- report is three shapes at once -- KPI scalars, per-amenity rows, and the
-- filter options -- and PostgREST returns one shape per call.
-- ---------------------------------------------------------------------------
create or replace function public.amenity_report_totals(
  p_community_id uuid,
  p_payload      jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_from   date := coalesce((nullif(p_payload ->> 'from_date', ''))::date, current_date - 30);
  v_to     date := coalesce((nullif(p_payload ->> 'to_date', ''))::date, current_date);
  v_result jsonb;
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may read the reports.'
      using errcode = '42501';
  end if;

  select jsonb_build_object(
    'kpis', (
      select jsonb_build_object(
        'total_bookings',    count(*),
        'approved_bookings', count(*) filter (where l.booking_status = 'approved'),
        'cancelled_bookings',count(*) filter (where l.booking_status = 'cancelled'),
        'total_charged',     coalesce(sum(l.total_amount), 0),
        'total_paid',        coalesce(sum(l.amount_paid), 0),
        'total_refunded',    coalesce(sum(l.refund_amount), 0)
      )
      from public.amenity_ledger_overview l
      where l.community_id = p_community_id
        and l.booking_date between v_from and v_to
    ),
    'rows', coalesce((
      select jsonb_agg(r order by r ->> 'amenity_name')
        from (
          select jsonb_build_object(
                   'amenity_id',    l.amenity_id,
                   'amenity_name',  l.amenity_name,
                   'booking_count', count(*),
                   'total_charged', coalesce(sum(l.total_amount), 0),
                   'total_paid',    coalesce(sum(l.amount_paid), 0)
                 ) as r
            from public.amenity_ledger_overview l
           where l.community_id = p_community_id
             and l.booking_date between v_from and v_to
           group by l.amenity_id, l.amenity_name
        ) s
    ), '[]'::jsonb),
    'options', jsonb_build_object(
      'amenities', coalesce((
        select jsonb_agg(jsonb_build_object('value', a.id, 'label', a.name) order by a.name)
          from public.amenities a where a.community_id = p_community_id
      ), '[]'::jsonb)
    ),
    'from_date', v_from,
    'to_date',   v_to
  ) into v_result;

  return v_result;
end $$;

grant execute on function public.save_amenity(uuid, uuid, jsonb)                to authenticated;
grant execute on function public.delete_amenity(uuid)                            to authenticated;
grant execute on function public.request_amenity_booking(uuid, jsonb)            to authenticated;
grant execute on function public.create_admin_amenity_booking(uuid, jsonb)       to authenticated;
grant execute on function public.block_amenity_slot(uuid, jsonb)                 to authenticated;
grant execute on function public.approve_amenity_booking(uuid)                   to authenticated;
grant execute on function public.reject_amenity_booking(uuid, jsonb)             to authenticated;
grant execute on function public.cancel_amenity_occurrences(jsonb)               to authenticated;
grant execute on function public.force_cancel_amenity_booking(uuid, jsonb)       to authenticated;
grant execute on function public.record_amenity_payment(uuid, jsonb)             to authenticated;
grant execute on function public.refund_amenity_deposit(uuid, jsonb)             to authenticated;
grant execute on function public.deduct_amenity_damage(uuid, jsonb)              to authenticated;
grant execute on function public.add_amenity_charge(uuid, jsonb)                 to authenticated;
grant execute on function public.amenity_report_totals(uuid, jsonb)              to authenticated;

-- ---------------------------------------------------------------------------
-- 15. Row-level security
-- ---------------------------------------------------------------------------
alter table public.amenity_bookings          enable row level security;
alter table public.amenity_booking_guests    enable row level security;
alter table public.amenity_booking_charges   enable row level security;
alter table public.amenity_financial_events  enable row level security;

drop policy if exists amenity_bookings_read on public.amenity_bookings;
create policy amenity_bookings_read on public.amenity_bookings
  for select to authenticated
  using (public.is_community_member(community_id));

drop policy if exists amenity_bookings_admin_write on public.amenity_bookings;
create policy amenity_bookings_admin_write on public.amenity_bookings
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

drop policy if exists amenity_booking_guests_read on public.amenity_booking_guests;
create policy amenity_booking_guests_read on public.amenity_booking_guests
  for select to authenticated
  using (public.is_community_member(community_id));

-- The ledger is admin-only. It records what residents were charged and refunded,
-- which is not a community-wide fact.
drop policy if exists amenity_booking_charges_read on public.amenity_booking_charges;
create policy amenity_booking_charges_read on public.amenity_booking_charges
  for select to authenticated
  using (public.is_community_admin(community_id));

drop policy if exists amenity_financial_events_read on public.amenity_financial_events;
create policy amenity_financial_events_read on public.amenity_financial_events
  for select to authenticated
  using (public.is_community_admin(community_id));

-- ---------------------------------------------------------------------------
-- 16. SSE outbox
-- ---------------------------------------------------------------------------
drop trigger if exists amenities_sse on public.amenities;
create trigger amenities_sse
  after insert or update or delete on public.amenities
  for each row execute function public.emit_dashboard_sse_event();

drop trigger if exists amenity_bookings_sse on public.amenity_bookings;
create trigger amenity_bookings_sse
  after insert or update or delete on public.amenity_bookings
  for each row execute function public.emit_dashboard_sse_event();
