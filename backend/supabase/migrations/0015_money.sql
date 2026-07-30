-- 0015_money.sql
-- Invoices, line items, payments and the payment audit stream, plus the
-- per-community billing settings the amounts come from.
--
-- Depends on 0010_memberships.sql (unit_residencies), 0011_dashboard_core.sql
-- and 0012_people.sql. Numbering: 0004-0009 belong to the auth/security
-- workstream (build plan 1.4).
--
-- ===========================================================================
-- THE ONE RULE THIS FILE IS BUILT AROUND
--
-- **Liability attaches to the unit, not to the person.** `invoices.unit_id` is
-- NOT NULL and there is no `invoices.membership_id`. A resident who moves out
-- does not take the flat's debt with them, and a new occupant does not inherit a
-- clean slate by moving in. `payments.payer_profile_id` records who actually
-- handed over the money, which is a different question and is answered
-- separately.
--
-- This is why the frontend's `payments[].userId` is a DISPLAY field on our side:
-- it is the flat's current primary resident, resolved at read time by the view.
-- It is not what the debt hangs from.
--
-- ===========================================================================
-- WHY THERE ARE FUNCTIONS IN HERE AND NOT JUST TABLES
--
-- Same reason as 0012: PostgREST has no client-side transaction, so every
-- .table(...).insert() is its own transaction. Issuing an invoice writes the
-- invoice AND its line items AND consumes an invoice number; recording a payment
-- writes the payment AND its event AND recomputes the invoice's outstanding
-- balance. A crash halfway through either one leaves money wrong, which is the
-- one category of wrong that cannot be shrugged off. Both are single RPCs.
--
-- SECURITY DEFINER means RLS does NOT run inside these functions, so each one
-- performs its own is_admin() + current_community_ids() check as its first act.
--
-- ===========================================================================
-- ARITHMETIC LIVES IN SQL, NOT IN PYTHON
--
-- Every total, every outstanding balance and every dashboard tile is computed by
-- Postgres in `numeric`, never by summing floats in the service layer. The API
-- emits floats because the React app does `amount.toLocaleString()` and
-- `reduce((a, c) => a + c.amount)` on the value -- a JSON string would be
-- silently concatenated into "42504250". So the wire format is lossy on purpose
-- and the database remains the only place arithmetic happens.
--
-- ===========================================================================
-- THREE DELIBERATE DEVIATIONS FROM THE ERD, EACH WITH A REASON
--
-- 1. `invoice_number` is unique PER COMMUNITY, not globally. The ERD marks it
--    globally unique, but the number is built from a per-community prefix that
--    defaults to 'INV' for everyone -- so under a global constraint the second
--    community to exist could never issue its first invoice.
--
-- 2. There is no 'overdue' STATUS. The ERD's InvoiceStatus lists one; a stored
--    overdue flag is correct only in the instant a cron job sets it and wrong
--    every hour after that. `invoice_overview.is_overdue` derives it from
--    `due_on` and `outstanding_amount`, which is right at every instant and
--    needs no scheduled job. A status that can never truthfully be written is
--    not left in the CHECK, because leaving it there invites someone to write it.
--
-- 3. `payments.payer_profile_id` is NULLABLE (the ERD says not null). An admin
--    recording cash for a flat whose resident has already moved out has no payer
--    to name, and forcing one would make them invent a person. The unit is the
--    debtor; the payer is optional enrichment.
--
-- ===========================================================================
-- WHAT IS DELIBERATELY *NOT* HERE: THE AUTO-SEEDED FIRST INVOICE
--
-- 0012 said the invoice half of "approve creates residency AND first invoice in
-- one transaction" would slot into approve_registration_request() here. It does
-- not, and the reason is that the premise changed underneath it.
--
-- The frontend seeds an unpaid invoice inside acceptRequest() because there,
-- approval CREATES AN ACTIVE RESIDENT. Ours does not: the standing ruling is
-- that the invite token is a mandatory second factor, so approval mints an
-- invitation and nothing else. Nobody has moved in at that moment. Seeding an
-- invoice there would put a receivable against a flat that may never be
-- occupied, and that receivable lands straight in the admin's "Outstanding
-- Receivables" tile as money that is not owed by anyone.
--
-- The equivalent moment in our flow is redemption, which is where a residency
-- would begin -- and redemption today creates a profile but no residency at all
-- (app/services/invitation_service.py), a gap in the auth workstream's half.
-- Billing is therefore explicit: run_maintenance_billing() bills every OCCUPIED
-- unit for a period, so a flat is billed once someone is actually living in it,
-- and is billed on the same cycle as every other flat rather than on the
-- anniversary of one approval. Raised as DECISIONS_NEEDED A13.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- community_billing_settings
--
-- WHY THIS TABLE EXISTS AT ALL: there is no maintenance amount anywhere in the
-- product. `createPendingRequestsSlice.js` hardcodes 4250 in the middle of an
-- approval handler, `data/payments.js` repeats it, and no screen configures it.
-- The ERD has no rate field either. So the first thing a real backend needs in
-- order to bill anyone did not exist, and it is created here.
--
-- NOT named `community_settings` even though the ERD has such a table, because
-- 0011 already chose a `community_modules` TABLE over the ERD's
-- `community_settings.enabled_modules` jsonb. That table is therefore already
-- not the shape the ERD describes, and claiming the name here would collide with
-- step 9, which owns settings. This one is money and nothing else.
-- ---------------------------------------------------------------------------
create table if not exists public.community_billing_settings (
  community_id              uuid primary key
                            references public.associations(id) on delete cascade,
  currency_code             char(3) not null default 'INR',
  invoice_number_prefix     text not null default 'INV',
  -- Nullable on purpose: a community that has not told us its rate must not be
  -- billed at a number we invented. run_maintenance_billing() refuses rather
  -- than guessing, and the admin gets a message saying which field to set.
  default_maintenance_amount numeric(12, 2),
  -- Capped at 28 so "the 30th" does not silently become "the 2nd of March"
  -- every February. A community wanting month-end gets the last day via the
  -- billing run's own p_due_on override.
  maintenance_due_day       smallint not null default 15,
  default_tax_percent       numeric(5, 2) not null default 0,
  -- Consumed under a row lock by next_invoice_number(). A sequence would be
  -- simpler but is global, and two communities must not interleave their
  -- invoice numbers.
  next_invoice_seq          bigint not null default 1,
  version                   integer not null default 1,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint community_billing_settings_due_day_ck
    check (maintenance_due_day between 1 and 28),
  constraint community_billing_settings_amount_ck
    check (default_maintenance_amount is null or default_maintenance_amount >= 0),
  constraint community_billing_settings_tax_ck
    check (default_tax_percent >= 0 and default_tax_percent < 100),
  constraint community_billing_settings_prefix_ck
    check (invoice_number_prefix ~ '^[A-Za-z0-9-]{1,12}$')
);

drop trigger if exists community_billing_settings_set_updated_at
  on public.community_billing_settings;
create trigger community_billing_settings_set_updated_at
  before update on public.community_billing_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- invoices
-- ---------------------------------------------------------------------------
create table if not exists public.invoices (
  id                        uuid primary key default gen_random_uuid(),
  community_id              uuid not null references public.associations(id) on delete cascade,
  -- NOT NULL, and the whole point of this file. See the header.
  unit_id                   uuid not null,
  invoice_number            text not null,
  invoice_type              text not null default 'maintenance',
  -- NOT in the ERD. The dashboard renders `payments[].title` verbatim
  -- ("Maintenance Fee - July 2026", "Clubhouse Event Charge"), and deriving it
  -- from type + period works for the first and not the second. Stored, so a
  -- one-off charge can say what it is.
  title                     text not null,
  status                    text not null default 'issued',
  billing_period_start      date,
  billing_period_end        date,
  issued_on                 date not null default current_date,
  due_on                    date not null,
  subtotal_amount           numeric(12, 2) not null default 0,
  tax_amount                numeric(12, 2) not null default 0,
  total_amount              numeric(12, 2) not null default 0,
  -- Maintained by record_payment() and void_invoice(), never by the API. The
  -- CHECK below makes an inconsistent balance impossible to store rather than
  -- merely unlikely.
  outstanding_amount        numeric(12, 2) not null default 0,
  currency_code             char(3) not null default 'INR',
  notes                     text,
  created_by_membership_id  uuid,
  voided_at                 timestamptz,
  void_reason               text,
  version                   integer not null default 1,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint invoices_status_ck
    check (status in ('draft', 'issued', 'partially_paid', 'paid', 'void')),
  constraint invoices_type_ck
    check (invoice_type in ('maintenance', 'amenity', 'penalty', 'misc')),
  constraint invoices_amounts_ck
    check (subtotal_amount >= 0 and tax_amount >= 0 and total_amount >= 0),
  constraint invoices_total_ck
    check (total_amount = subtotal_amount + tax_amount),
  constraint invoices_outstanding_ck
    check (outstanding_amount >= 0 and outstanding_amount <= total_amount),
  -- A paid invoice with a balance, or a settled invoice still marked issued, are
  -- both states the API could reach through a bug. Neither can be stored. This
  -- is why issue_invoice() inserts as 'draft' and promotes to 'issued' only once
  -- the line items have given the invoice an amount.
  constraint invoices_status_balance_ck check (
    case status
      when 'paid'  then outstanding_amount = 0
      when 'void'  then true
      when 'draft' then true
      else outstanding_amount > 0
    end
  ),
  constraint invoices_period_ck check (
    billing_period_start is null or billing_period_end is null
    or billing_period_end >= billing_period_start
  ),
  constraint invoices_due_ck check (due_on >= issued_on),
  constraint invoices_number_community_uq unique (community_id, invoice_number),
  constraint invoices_id_community_uq unique (id, community_id),
  constraint invoices_unit_fk
    foreign key (unit_id, community_id)
    references public.apartments (id, association_id) on delete cascade,
  constraint invoices_created_by_fk
    foreign key (created_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (created_by_membership_id)
);

-- THE DOUBLE-BILLING GUARD, and the most load-bearing line in this file.
--
-- One live maintenance invoice per flat per billing period. Without it, a
-- double-clicked "run billing" bills every flat in the community twice and the
-- only evidence is in the residents' invoice lists. Partial on `status <>
-- 'void'` so a voided invoice can be reissued for the same period.
create unique index if not exists invoices_maintenance_period_uq
  on public.invoices (community_id, unit_id, billing_period_start)
  where invoice_type = 'maintenance' and status <> 'void';

create index if not exists invoices_community_status_idx
  on public.invoices (community_id, status, due_on);
create index if not exists invoices_unit_idx on public.invoices (unit_id, issued_on desc);
-- Drives the "Outstanding Receivables" tile without scanning settled history.
create index if not exists invoices_outstanding_idx
  on public.invoices (community_id, due_on)
  where outstanding_amount > 0 and status <> 'void';

drop trigger if exists invoices_set_updated_at on public.invoices;
create trigger invoices_set_updated_at
  before update on public.invoices
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- invoice_line_items
--
-- `amenity_booking_charge_id` from the ERD is NOT added yet: the table it
-- references arrives in step 8, and a nullable column with no foreign key is a
-- pointer nothing checks. It is a one-line ALTER when amenities land.
-- ---------------------------------------------------------------------------
create table if not exists public.invoice_line_items (
  id            uuid primary key default gen_random_uuid(),
  community_id  uuid not null references public.associations(id) on delete cascade,
  invoice_id    uuid not null,
  description   text not null,
  quantity      numeric(10, 2) not null default 1,
  unit_amount   numeric(12, 2) not null,
  total_amount  numeric(12, 2) not null,
  sort_order    smallint not null default 0,
  created_at    timestamptz not null default now(),
  constraint invoice_line_items_quantity_ck check (quantity > 0),
  -- The line's own total must agree with its own inputs. Rounded to 2dp because
  -- quantity is itself fractional and 3 x 33.33 must not have to be exact.
  constraint invoice_line_items_total_ck
    check (total_amount = round(quantity * unit_amount, 2)),
  constraint invoice_line_items_invoice_fk
    foreign key (invoice_id, community_id)
    references public.invoices (id, community_id) on delete cascade
);

create index if not exists invoice_line_items_invoice_idx
  on public.invoice_line_items (invoice_id, sort_order);

-- ---------------------------------------------------------------------------
-- payments
-- ---------------------------------------------------------------------------
create table if not exists public.payments (
  id                        uuid primary key default gen_random_uuid(),
  community_id              uuid not null references public.associations(id) on delete cascade,
  invoice_id                uuid not null,
  -- Nullable -- see deviation 3 in the header.
  payer_profile_id          uuid references public.profiles(id) on delete set null,
  received_by_membership_id uuid,
  amount                    numeric(12, 2) not null,
  currency_code             char(3) not null default 'INR',
  payment_method            text not null,
  -- The provider's own transaction id. UNIQUE per community so a replayed
  -- webhook or a double-submitted form is a no-op instead of a second credit --
  -- record_payment() returns the existing row rather than raising.
  provider_reference        text,
  status                    text not null default 'succeeded',
  paid_at                   timestamptz not null default now(),
  notes                     text,
  version                   integer not null default 1,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  constraint payments_amount_ck check (amount > 0),
  constraint payments_status_ck
    check (status in ('initiated', 'succeeded', 'failed', 'refunded')),
  constraint payments_method_ck check (payment_method in (
    'upi', 'card', 'netbanking', 'cash', 'cheque', 'bank_transfer'
  )),
  constraint payments_id_community_uq unique (id, community_id),
  constraint payments_invoice_fk
    foreign key (invoice_id, community_id)
    references public.invoices (id, community_id) on delete cascade,
  constraint payments_received_by_fk
    foreign key (received_by_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (received_by_membership_id)
);

-- Partial, so the many payments with no provider reference (cash, cheque) do not
-- all collide on NULL... which they would not anyway, but stating it partial
-- makes the intent explicit and keeps the index small.
create unique index if not exists payments_provider_reference_uq
  on public.payments (community_id, provider_reference)
  where provider_reference is not null;

create index if not exists payments_invoice_idx on public.payments (invoice_id, paid_at desc);
create index if not exists payments_community_idx
  on public.payments (community_id, paid_at desc) where status = 'succeeded';

drop trigger if exists payments_set_updated_at on public.payments;
create trigger payments_set_updated_at
  before update on public.payments
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- payment_events
--
-- APPEND-ONLY, enforced the same way complaint_events is: no UPDATE or DELETE
-- policy below and no updated_at column. For money this is not a nicety -- it is
-- the only record of why a balance changed.
-- ---------------------------------------------------------------------------
create table if not exists public.payment_events (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.associations(id) on delete cascade,
  payment_id          uuid not null,
  actor_membership_id uuid,
  event_type          text not null,
  previous_status     text,
  new_status          text,
  metadata            jsonb,
  created_at          timestamptz not null default now(),
  constraint payment_events_type_ck check (event_type in (
    'initiated', 'succeeded', 'failed', 'refunded', 'recorded', 'reconciled'
  )),
  constraint payment_events_payment_fk
    foreign key (payment_id, community_id)
    references public.payments (id, community_id) on delete cascade,
  constraint payment_events_actor_fk
    foreign key (actor_membership_id, community_id)
    references public.community_memberships (id, community_id)
    on delete set null (actor_membership_id)
);

create index if not exists payment_events_payment_idx
  on public.payment_events (payment_id, created_at);

-- ---------------------------------------------------------------------------
-- current_unit_ids -- the flats the caller currently lives in.
--
-- SECURITY DEFINER for the same reason as current_community_ids(): a policy on
-- `invoices` that queried `unit_residencies` through RLS would recurse.
-- ---------------------------------------------------------------------------
create or replace function public.current_unit_ids()
returns table (unit_id uuid, start_date date)
language sql
stable
security definer
set search_path = public
as $$
  select r.unit_id, min(r.start_date)
    from public.unit_residencies r
    join public.community_memberships m
      on m.id = r.membership_id and m.status = 'active'
   where m.profile_id = auth.uid()
     and r.end_date is null
   group by r.unit_id;
$$;

revoke execute on function public.current_unit_ids() from public, anon;
grant execute on function public.current_unit_ids() to authenticated;

-- ---------------------------------------------------------------------------
-- ensure_billing_settings -- find-or-create the settings row.
--
-- Every community gets one lazily rather than by backfill, so a community
-- created by another workstream after this migration is not missing it.
-- ---------------------------------------------------------------------------
create or replace function public.ensure_billing_settings(p_community_id uuid)
returns public.community_billing_settings
language plpgsql
security definer
set search_path = public
as $$
declare
  settings public.community_billing_settings%rowtype;
begin
  insert into public.community_billing_settings (community_id)
  values (p_community_id)
  on conflict (community_id) do nothing;

  select * into settings
    from public.community_billing_settings
   where community_id = p_community_id;

  return settings;
end;
$$;

-- ---------------------------------------------------------------------------
-- next_invoice_number -- consume one number from the community's counter.
--
-- The increment is done BY the UPDATE rather than by reading the value and
-- writing it back, so the row lock the UPDATE takes is what serialises two
-- invoices issued in the same millisecond -- they cannot both read the same
-- `next_invoice_seq`. RETURNING sees the new value, hence the `- 1`.
--
-- Called inside run_maintenance_billing()'s per-unit exception block, which is a
-- subtransaction: a unit skipped for already being billed rolls the increment
-- back with it, so skipped flats do not burn invoice numbers.
-- ---------------------------------------------------------------------------
create or replace function public.next_invoice_number(p_community_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_prefix text;
  v_seq    bigint;
begin
  perform public.ensure_billing_settings(p_community_id);

  update public.community_billing_settings
     set next_invoice_seq = next_invoice_seq + 1
   where community_id = p_community_id
  returning invoice_number_prefix, next_invoice_seq - 1 into v_prefix, v_seq;

  return v_prefix || '-' || to_char(current_date, 'YYYY') || '-' || lpad(v_seq::text, 5, '0');
end;
$$;

-- ---------------------------------------------------------------------------
-- invoice_overview
--
-- `security_invoker = true` (PG15+) so the view is filtered by the CALLER's RLS
-- rather than the view owner's. Without it a view over an RLS-protected table is
-- a hole straight through that protection.
--
-- Exists rather than being an RPC because a list endpoint needs filtering,
-- ordering, paging and an exact count, and PostgREST gives all four free on a
-- view. An RPC would have to reimplement each as a parameter.
-- ---------------------------------------------------------------------------
create or replace view public.invoice_overview
with (security_invoker = true) as
select
  i.id,
  i.community_id,
  i.unit_id,
  i.invoice_number,
  i.invoice_type,
  i.title,
  i.status,
  i.billing_period_start,
  i.billing_period_end,
  i.issued_on,
  i.due_on,
  i.subtotal_amount,
  i.tax_amount,
  i.total_amount,
  i.outstanding_amount,
  (i.total_amount - i.outstanding_amount) as amount_paid,
  i.currency_code,
  i.notes,
  i.created_at,
  i.updated_at,
  a.code as unit_code,
  -- 'B-1204' -> 'B'. The dashboard renders `Tower {tower} - Flat {flat}` from two
  -- separate fields, so the split has to happen somewhere; here, once, rather
  -- than in every caller.
  nullif(split_part(a.code, '-', 1), a.code) as tower,
  res.membership_id as resident_membership_id,
  res.profile_id    as resident_profile_id,
  res.display_name  as resident_name,
  paid.paid_at        as paid_on,
  paid.payment_method as payment_method,
  -- DERIVED, never stored -- deviation 2 in the header.
  (i.status <> 'void' and i.outstanding_amount > 0 and i.due_on < current_date)
    as is_overdue,
  lower(concat_ws(' ', i.title, i.invoice_number, a.code, res.display_name))
    as search_text
from public.invoices i
left join public.apartments a on a.id = i.unit_id
-- The flat's current occupant, for display only. `is_primary desc` first because
-- that is the billing contact; `start_date` breaks the tie for a flat whose
-- primary slot is empty.
left join lateral (
  select m.id as membership_id, p.id as profile_id, p.full_name as display_name
    from public.unit_residencies r
    join public.community_memberships m
      on m.id = r.membership_id and m.status = 'active'
    join public.profiles p on p.id = m.profile_id
   where r.unit_id = i.unit_id and r.end_date is null
   order by r.is_primary desc, r.start_date, r.created_at
   limit 1
) res on true
-- The settling payment, for the frontend's `paidOn` / `paymentMethod` fields.
-- The LATEST succeeded one: a partially paid invoice shows its most recent
-- payment, and a fully paid one shows the payment that closed it.
left join lateral (
  select pay.paid_at, pay.payment_method
    from public.payments pay
   where pay.invoice_id = i.id and pay.status = 'succeeded'
   order by pay.paid_at desc, pay.created_at desc
   limit 1
) paid on true;

-- ---------------------------------------------------------------------------
-- payment_overview -- the "online fee collection log" the Maintenance screen
-- names in its subtitle but never renders.
-- ---------------------------------------------------------------------------
create or replace view public.payment_overview
with (security_invoker = true) as
select
  pay.id,
  pay.community_id,
  pay.invoice_id,
  pay.amount,
  pay.currency_code,
  pay.payment_method,
  pay.provider_reference,
  pay.status,
  pay.paid_at,
  pay.notes,
  pay.created_at,
  i.invoice_number,
  i.title as invoice_title,
  i.unit_id,
  a.code as unit_code,
  pay.payer_profile_id,
  payer.full_name as payer_name,
  pay.received_by_membership_id,
  lower(concat_ws(' ', i.invoice_number, i.title, a.code, payer.full_name,
                  pay.provider_reference)) as search_text
from public.payments pay
join public.invoices i on i.id = pay.invoice_id
left join public.apartments a on a.id = i.unit_id
left join public.profiles payer on payer.id = pay.payer_profile_id;

-- ---------------------------------------------------------------------------
-- collection_summary -- the three tiles at the top of the Maintenance screen.
--
-- A VIEW rather than three counting queries, and a database aggregate rather
-- than a loop in the service layer, for the reason at the top of this file:
-- money is summed in `numeric` by Postgres exactly once. Summing a page of
-- floats in Python would give a number that is both wrong and plausible.
--
-- Note what `total_outstanding` sums: the BALANCES, not the amounts of unpaid
-- invoices. A partially paid invoice contributes only what is still owed. The
-- frontend cannot make that distinction -- it sums `amount` over rows whose
-- status is 'Unpaid' -- so its receivables tile reads high the moment a partial
-- payment exists.
--
-- Voided invoices are excluded from every figure: a cancelled bill is neither
-- collected nor collectable.
-- ---------------------------------------------------------------------------
create or replace view public.collection_summary
with (security_invoker = true) as
select
  i.community_id,
  coalesce(sum(i.total_amount - i.outstanding_amount), 0)     as total_collected,
  coalesce(sum(i.outstanding_amount), 0)                      as total_outstanding,
  coalesce(sum(i.total_amount), 0)                            as total_billed,
  count(*) filter (where i.status = 'paid')                   as paid_count,
  count(*) filter (where i.status <> 'paid')                  as unpaid_count,
  count(*)                                                    as invoice_count,
  count(*) filter (
    where i.outstanding_amount > 0 and i.due_on < current_date
  )                                                           as overdue_count,
  coalesce(sum(i.outstanding_amount) filter (
    where i.outstanding_amount > 0 and i.due_on < current_date
  ), 0)                                                       as overdue_amount,
  min(i.currency_code)                                        as currency_code
from public.invoices i
where i.status <> 'void'
group by i.community_id;

-- ---------------------------------------------------------------------------
-- assert_billing_admin -- the authorization check every RPC below opens with.
--
-- Extracted because five functions repeat it, and a check that is copy-pasted
-- five times is a check that will eventually be pasted four times.
-- ---------------------------------------------------------------------------
create or replace function public.assert_billing_admin(p_community_id uuid)
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

-- ---------------------------------------------------------------------------
-- recalculate_invoice_balance -- the single writer of outstanding_amount.
--
-- Recomputed from the payment rows rather than decremented, so a failed or
-- refunded payment corrects the balance instead of leaving it drifting. Called
-- inside record_payment(), never from the API.
-- ---------------------------------------------------------------------------
create or replace function public.recalculate_invoice_balance(p_invoice_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  inv       public.invoices%rowtype;
  v_settled numeric(12, 2);
begin
  select * into inv from public.invoices where id = p_invoice_id for update;
  if not found then
    raise exception 'Invoice not found.' using errcode = 'HB404';
  end if;

  -- A void invoice keeps whatever balance it had; its status is terminal and
  -- recomputing it would resurrect a bill somebody has already cancelled.
  if inv.status = 'void' then
    return;
  end if;

  select coalesce(sum(amount), 0) into v_settled
    from public.payments
   where invoice_id = p_invoice_id and status = 'succeeded';

  -- least(): an overpayment must not drive the balance negative, which the
  -- invoices_outstanding_ck CHECK would reject anyway -- as a 500, rather than
  -- as the "paid in full" this actually is.
  update public.invoices
     set outstanding_amount = greatest(total_amount - least(v_settled, total_amount), 0),
         status = case
           when v_settled >= total_amount then 'paid'
           when v_settled > 0             then 'partially_paid'
           else 'issued'
         end
   where id = p_invoice_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- issue_invoice
--
-- Creates the invoice, its line items and its number in one transaction, and
-- computes the totals from the lines so the API cannot submit an invoice whose
-- header disagrees with its own contents.
--
-- p_payload keys: unit_code | unit_id, title, invoice_type, due_on, issued_on,
--   billing_period_start, billing_period_end, notes, tax_percent,
--   lines: [{description, quantity, unit_amount}]
-- ---------------------------------------------------------------------------
create or replace function public.issue_invoice(
  p_community_id uuid,
  p_payload      jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_unit_id     uuid;
  v_invoice_id  uuid;
  v_subtotal    numeric(12, 2) := 0;
  v_tax_percent numeric(5, 2);
  v_tax         numeric(12, 2);
  v_issued_on   date;
  v_due_on      date;
  v_settings    public.community_billing_settings%rowtype;
  v_actor       uuid;
  v_line        jsonb;
  v_sort        smallint := 0;
begin
  perform public.assert_billing_admin(p_community_id);
  v_settings := public.ensure_billing_settings(p_community_id);

  -- Find-or-create the flat by code: the frontend has never had a flat-creation
  -- step, so an invoice may name a unit that does not exist yet. Same rule the
  -- registration approval uses.
  if p_payload ? 'unit_id' and nullif(p_payload ->> 'unit_id', '') is not null then
    v_unit_id := (p_payload ->> 'unit_id')::uuid;
  else
    insert into public.apartments (association_id, code)
    values (p_community_id, trim(p_payload ->> 'unit_code'))
    on conflict (association_id, code) do nothing;

    select id into v_unit_id
      from public.apartments
     where association_id = p_community_id and code = trim(p_payload ->> 'unit_code');
  end if;

  if v_unit_id is null then
    raise exception 'That flat could not be resolved.' using errcode = 'HB404';
  end if;

  -- Tenancy of the unit itself, explicitly: the composite FK below would catch a
  -- cross-community unit_id, but as a foreign-key violation, which reads to the
  -- caller as a 400 about a constraint rather than "no such flat here".
  if not exists (
    select 1 from public.apartments
     where id = v_unit_id and association_id = p_community_id
  ) then
    raise exception 'That flat belongs to a different community.' using errcode = 'HB403';
  end if;

  v_issued_on := coalesce((p_payload ->> 'issued_on')::date, current_date);
  v_due_on    := coalesce(
    (p_payload ->> 'due_on')::date,
    v_issued_on + interval '15 days'
  );

  if v_due_on < v_issued_on then
    raise exception 'The due date cannot be before the issue date.' using errcode = 'HB409';
  end if;

  select id into v_actor
    from public.community_memberships
   where community_id = p_community_id and profile_id = auth.uid()
   limit 1;

  insert into public.invoices (
    community_id, unit_id, invoice_number, invoice_type, title, status,
    billing_period_start, billing_period_end, issued_on, due_on,
    subtotal_amount, tax_amount, total_amount, outstanding_amount,
    currency_code, notes, created_by_membership_id
  )
  values (
    p_community_id,
    v_unit_id,
    public.next_invoice_number(p_community_id),
    coalesce(nullif(p_payload ->> 'invoice_type', ''), 'maintenance'),
    coalesce(nullif(trim(p_payload ->> 'title'), ''), 'Invoice'),
    -- 'draft' until the lines exist: invoices_status_balance_ck forbids an
    -- issued invoice with nothing outstanding, and at this point there is
    -- nothing on it yet.
    'draft',
    (p_payload ->> 'billing_period_start')::date,
    (p_payload ->> 'billing_period_end')::date,
    v_issued_on,
    v_due_on,
    0, 0, 0, 0,
    v_settings.currency_code,
    nullif(p_payload ->> 'notes', ''),
    v_actor
  )
  returning id into v_invoice_id;

  for v_line in select * from jsonb_array_elements(coalesce(p_payload -> 'lines', '[]'::jsonb))
  loop
    insert into public.invoice_line_items (
      community_id, invoice_id, description, quantity, unit_amount, total_amount, sort_order
    )
    values (
      p_community_id,
      v_invoice_id,
      coalesce(nullif(trim(v_line ->> 'description'), ''), 'Charge'),
      coalesce((v_line ->> 'quantity')::numeric, 1),
      (v_line ->> 'unit_amount')::numeric,
      round(coalesce((v_line ->> 'quantity')::numeric, 1) * (v_line ->> 'unit_amount')::numeric, 2),
      v_sort
    );
    v_sort := v_sort + 1;
  end loop;

  select coalesce(sum(total_amount), 0) into v_subtotal
    from public.invoice_line_items where invoice_id = v_invoice_id;

  if v_subtotal <= 0 then
    raise exception 'An invoice needs at least one line with an amount above zero.'
      using errcode = 'HB409';
  end if;

  v_tax_percent := coalesce(
    (p_payload ->> 'tax_percent')::numeric, v_settings.default_tax_percent
  );
  v_tax := round(v_subtotal * v_tax_percent / 100, 2);

  update public.invoices
     set subtotal_amount    = v_subtotal,
         tax_amount         = v_tax,
         total_amount       = v_subtotal + v_tax,
         outstanding_amount = v_subtotal + v_tax,
         status             = 'issued'
   where id = v_invoice_id;

  return v_invoice_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- run_maintenance_billing
--
-- One maintenance invoice per OCCUPIED unit for a billing period.
--
-- WHY OCCUPANCY DECIDES WHO IS BILLED: a real association bills the OWNER, and
-- an empty flat still owes maintenance. But nothing in this product records
-- ownership -- `unit_residencies.relationship` can say 'owner', yet a vacant
-- flat has no residency row at all, so an absent owner is invisible. Occupancy
-- is the only signal that exists. Raised as DECISIONS_NEEDED A14.
--
-- Re-running for the same period is SAFE: invoices_maintenance_period_uq makes
-- the duplicate insert impossible, and the loop counts it as skipped rather than
-- failing the whole run. So a double-clicked button bills nobody twice.
-- ---------------------------------------------------------------------------
create or replace function public.run_maintenance_billing(
  p_community_id uuid,
  p_payload      jsonb
)
returns table (invoiced integer, skipped integer, total_amount numeric)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_settings     public.community_billing_settings%rowtype;
  v_amount       numeric(12, 2);
  v_period_start date;
  v_period_end   date;
  v_due_on       date;
  v_title        text;
  v_invoiced     integer := 0;
  v_skipped      integer := 0;
  v_total        numeric(12, 2) := 0;
  v_unit         record;
  v_invoice_id   uuid;
begin
  perform public.assert_billing_admin(p_community_id);
  v_settings := public.ensure_billing_settings(p_community_id);

  v_amount := coalesce(
    (p_payload ->> 'amount')::numeric, v_settings.default_maintenance_amount
  );

  -- Refuse rather than invent. The frontend's hardcoded 4250 is a demo value,
  -- and silently adopting it would bill a real community a number nobody chose.
  if v_amount is null or v_amount <= 0 then
    raise exception
      'Set a maintenance amount before running billing (billing settings, defaultMaintenanceAmount).'
      using errcode = 'HB409';
  end if;

  v_period_start := coalesce(
    (p_payload ->> 'period_start')::date, date_trunc('month', current_date)::date
  );
  v_period_end := coalesce(
    (p_payload ->> 'period_end')::date,
    (date_trunc('month', v_period_start) + interval '1 month - 1 day')::date
  );
  v_due_on := coalesce(
    (p_payload ->> 'due_on')::date,
    date_trunc('month', v_period_start)::date + (v_settings.maintenance_due_day - 1)
  );

  if v_due_on < current_date then
    v_due_on := current_date;
  end if;

  v_title := coalesce(
    nullif(trim(p_payload ->> 'title'), ''),
    'Maintenance Fee - ' || to_char(v_period_start, 'FMMonth YYYY')
  );

  for v_unit in
    select distinct a.id, a.code
      from public.apartments a
      join public.unit_residencies r
        on r.unit_id = a.id and r.end_date is null
     where a.association_id = p_community_id
     order by a.code
  loop
    begin
      insert into public.invoices (
        community_id, unit_id, invoice_number, invoice_type, title, status,
        billing_period_start, billing_period_end, issued_on, due_on,
        subtotal_amount, tax_amount, total_amount, outstanding_amount, currency_code
      )
      values (
        p_community_id, v_unit.id, public.next_invoice_number(p_community_id),
        'maintenance', v_title, 'issued',
        v_period_start, v_period_end, current_date, v_due_on,
        v_amount, 0, v_amount, v_amount, v_settings.currency_code
      )
      returning id into v_invoice_id;

      insert into public.invoice_line_items (
        community_id, invoice_id, description, quantity, unit_amount, total_amount
      )
      values (p_community_id, v_invoice_id, v_title, 1, v_amount, v_amount);

      v_invoiced := v_invoiced + 1;
      v_total := v_total + v_amount;
    exception
      -- Already billed for this period. Caught per unit, so one duplicate does
      -- not abort the other 199 flats.
      when unique_violation then
        v_skipped := v_skipped + 1;
    end;
  end loop;

  return query select v_invoiced, v_skipped, v_total;
end;
$$;

-- ---------------------------------------------------------------------------
-- record_payment
--
-- Writes the payment, appends its event and recomputes the invoice balance in
-- one transaction.
--
-- IDEMPOTENT on provider_reference: a replayed gateway webhook, or a resident
-- double-tapping "Pay", returns the payment already recorded instead of
-- crediting the invoice twice. This is checked BEFORE the insert as well as
-- being enforced by the unique index, so the caller gets the existing id rather
-- than a 409 they would have to interpret.
--
-- p_payload keys: amount, payment_method, provider_reference, payer_profile_id,
--   paid_at, notes, status
-- ---------------------------------------------------------------------------
create or replace function public.record_payment(
  p_invoice_id uuid,
  p_payload    jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  inv          public.invoices%rowtype;
  v_payment_id uuid;
  v_amount     numeric(12, 2);
  v_reference  text;
  v_status     text;
  v_actor      uuid;
begin
  select * into inv from public.invoices where id = p_invoice_id for update;
  if not found then
    raise exception 'Invoice not found.' using errcode = 'HB404';
  end if;

  perform public.assert_billing_admin(inv.community_id);

  if inv.status = 'void' then
    raise exception 'This invoice has been voided and cannot take a payment.'
      using errcode = 'HB409';
  end if;

  v_reference := nullif(trim(p_payload ->> 'provider_reference'), '');
  if v_reference is not null then
    select id into v_payment_id
      from public.payments
     where community_id = inv.community_id and provider_reference = v_reference;
    if v_payment_id is not null then
      return v_payment_id;
    end if;
  end if;

  v_amount := (p_payload ->> 'amount')::numeric;
  if v_amount is null or v_amount <= 0 then
    raise exception 'A payment amount must be above zero.' using errcode = 'HB409';
  end if;

  -- Overpayment is refused rather than absorbed. `recalculate_invoice_balance`
  -- would clamp it and the money would vanish from the ledger while appearing to
  -- have been accepted, which is the worst of the available outcomes.
  if v_amount > inv.outstanding_amount then
    raise exception 'That is more than the % outstanding on this invoice.',
      inv.outstanding_amount using errcode = 'HB409';
  end if;

  v_status := coalesce(nullif(p_payload ->> 'status', ''), 'succeeded');

  select id into v_actor
    from public.community_memberships
   where community_id = inv.community_id and profile_id = auth.uid()
   limit 1;

  insert into public.payments (
    community_id, invoice_id, payer_profile_id, received_by_membership_id,
    amount, currency_code, payment_method, provider_reference, status, paid_at, notes
  )
  values (
    inv.community_id,
    p_invoice_id,
    nullif(p_payload ->> 'payer_profile_id', '')::uuid,
    v_actor,
    v_amount,
    inv.currency_code,
    coalesce(nullif(p_payload ->> 'payment_method', ''), 'cash'),
    v_reference,
    v_status,
    coalesce((p_payload ->> 'paid_at')::timestamptz, now()),
    nullif(p_payload ->> 'notes', '')
  )
  returning id into v_payment_id;

  insert into public.payment_events (
    community_id, payment_id, actor_membership_id, event_type, new_status, metadata
  )
  values (
    inv.community_id, v_payment_id, v_actor, 'recorded', v_status,
    jsonb_build_object('amount', v_amount, 'invoice_number', inv.invoice_number)
  );

  perform public.recalculate_invoice_balance(p_invoice_id);

  return v_payment_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- void_invoice
--
-- Money records are never deleted. Voiding leaves the invoice, its lines and its
-- number in place and marks it cancelled -- an invoice number that disappears is
-- a gap an auditor has to explain.
--
-- Refused once any payment has succeeded against it: cancelling a bill somebody
-- has already paid would strand their money against nothing. Refund first.
-- ---------------------------------------------------------------------------
create or replace function public.void_invoice(p_invoice_id uuid, p_reason text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  inv     public.invoices%rowtype;
  v_paid  numeric(12, 2);
begin
  select * into inv from public.invoices where id = p_invoice_id for update;
  if not found then
    raise exception 'Invoice not found.' using errcode = 'HB404';
  end if;

  perform public.assert_billing_admin(inv.community_id);

  if inv.status = 'void' then
    raise exception 'This invoice is already void.' using errcode = 'HB409';
  end if;

  select coalesce(sum(amount), 0) into v_paid
    from public.payments
   where invoice_id = p_invoice_id and status = 'succeeded';

  if v_paid > 0 then
    raise exception 'This invoice has payments against it and cannot be voided.'
      using errcode = 'HB409';
  end if;

  update public.invoices
     set status = 'void',
         outstanding_amount = 0,
         voided_at = now(),
         void_reason = nullif(trim(p_reason), '')
   where id = p_invoice_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- update_billing_settings -- an RPC rather than a table write so the settings
-- row is created on first use and the authorization check is not left to RLS
-- alone on a table an admin could otherwise reach for another community.
-- ---------------------------------------------------------------------------
create or replace function public.update_billing_settings(
  p_community_id uuid,
  p_patch        jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.assert_billing_admin(p_community_id);
  perform public.ensure_billing_settings(p_community_id);

  update public.community_billing_settings x
     set currency_code = case when p_patch ? 'currency_code'
           then upper(p_patch ->> 'currency_code') else x.currency_code end,
         invoice_number_prefix = case when p_patch ? 'invoice_number_prefix'
           then upper(p_patch ->> 'invoice_number_prefix') else x.invoice_number_prefix end,
         -- Key PRESENCE, not value: `{"default_maintenance_amount": null}` clears
         -- the rate, an absent key leaves it alone. Matches the API's
         -- model_dump(exclude_unset=True).
         default_maintenance_amount = case when p_patch ? 'default_maintenance_amount'
           then (p_patch ->> 'default_maintenance_amount')::numeric
           else x.default_maintenance_amount end,
         maintenance_due_day = case when p_patch ? 'maintenance_due_day'
           then (p_patch ->> 'maintenance_due_day')::smallint else x.maintenance_due_day end,
         default_tax_percent = case when p_patch ? 'default_tax_percent'
           then (p_patch ->> 'default_tax_percent')::numeric else x.default_tax_percent end,
         version = x.version + 1
   where x.community_id = p_community_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Grants. Internal helpers are reachable only from the RPCs above, which run as
-- owner -- nothing outside this file should be able to move a balance.
-- ---------------------------------------------------------------------------
revoke execute on function public.ensure_billing_settings(uuid) from public, anon, authenticated;
revoke execute on function public.next_invoice_number(uuid) from public, anon, authenticated;
revoke execute on function public.recalculate_invoice_balance(uuid) from public, anon, authenticated;
revoke execute on function public.assert_billing_admin(uuid) from public, anon, authenticated;

revoke execute on function public.issue_invoice(uuid, jsonb) from public, anon;
revoke execute on function public.run_maintenance_billing(uuid, jsonb) from public, anon;
revoke execute on function public.record_payment(uuid, jsonb) from public, anon;
revoke execute on function public.void_invoice(uuid, text) from public, anon;
revoke execute on function public.update_billing_settings(uuid, jsonb) from public, anon;

grant execute on function public.issue_invoice(uuid, jsonb) to authenticated;
grant execute on function public.run_maintenance_billing(uuid, jsonb) to authenticated;
grant execute on function public.record_payment(uuid, jsonb) to authenticated;
grant execute on function public.void_invoice(uuid, text) to authenticated;
grant execute on function public.update_billing_settings(uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- The resident read policy is narrower than "invoices for my flat", on purpose:
-- it is bounded by `issued_on >= start_date`. Liability follows the unit, so a
-- flat's invoice history outlives its occupants -- and showing a new tenant the
-- previous occupant's arrears would disclose one resident's debts to another.
-- ---------------------------------------------------------------------------
alter table public.community_billing_settings enable row level security;
alter table public.invoices enable row level security;
alter table public.invoice_line_items enable row level security;
alter table public.payments enable row level security;
alter table public.payment_events enable row level security;

drop policy if exists billing_settings_admin_all on public.community_billing_settings;
create policy billing_settings_admin_all on public.community_billing_settings
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists invoices_admin_all on public.invoices;
create policy invoices_admin_all on public.invoices
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists invoices_resident_read on public.invoices;
create policy invoices_resident_read on public.invoices
  for select using (
    exists (
      select 1 from public.current_unit_ids() u
       where u.unit_id = invoices.unit_id
         and invoices.issued_on >= u.start_date
    )
  );

drop policy if exists invoice_line_items_admin_all on public.invoice_line_items;
create policy invoice_line_items_admin_all on public.invoice_line_items
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists invoice_line_items_resident_read on public.invoice_line_items;
create policy invoice_line_items_resident_read on public.invoice_line_items
  for select using (
    exists (
      select 1
        from public.invoices i
        join public.current_unit_ids() u on u.unit_id = i.unit_id
       where i.id = invoice_line_items.invoice_id
         and i.issued_on >= u.start_date
    )
  );

drop policy if exists payments_admin_all on public.payments;
create policy payments_admin_all on public.payments
  for all
  using (public.is_admin() and community_id in (select public.current_community_ids()))
  with check (public.is_admin() and community_id in (select public.current_community_ids()));

drop policy if exists payments_resident_read on public.payments;
create policy payments_resident_read on public.payments
  for select using (
    exists (
      select 1
        from public.invoices i
        join public.current_unit_ids() u on u.unit_id = i.unit_id
       where i.id = payments.invoice_id
         and i.issued_on >= u.start_date
    )
  );

-- Append-only: SELECT and INSERT policies only. No UPDATE, no DELETE, for
-- anybody -- including admins.
drop policy if exists payment_events_admin_read on public.payment_events;
create policy payment_events_admin_read on public.payment_events
  for select using (
    public.is_admin() and community_id in (select public.current_community_ids())
  );

drop policy if exists payment_events_admin_insert on public.payment_events;
create policy payment_events_admin_insert on public.payment_events
  for insert with check (
    public.is_admin() and community_id in (select public.current_community_ids())
  );

-- ---------------------------------------------------------------------------
-- Verification -- run after applying. Each should return zero rows unless noted.
-- ---------------------------------------------------------------------------
-- All three views are security_invoker (expect three rows, all 'true'):
--   select c.relname, (select option_value from pg_options_to_table(c.reloptions)
--                       where option_name = 'security_invoker')
--   from pg_class c
--   where c.relname in ('invoice_overview', 'payment_overview', 'collection_summary');
--
-- The summary agrees with a direct count (expect one row, all three matching):
--   select s.total_billed, s.total_collected, s.total_outstanding,
--          (select sum(total_amount) from public.invoices
--            where community_id = s.community_id and status <> 'void'),
--          (select sum(total_amount - outstanding_amount) from public.invoices
--            where community_id = s.community_id and status <> 'void'),
--          (select sum(outstanding_amount) from public.invoices
--            where community_id = s.community_id and status <> 'void')
--   from public.collection_summary s;
--
-- No invoice header disagrees with its own line items:
--   select i.id, i.subtotal_amount, sum(l.total_amount)
--   from public.invoices i join public.invoice_line_items l on l.invoice_id = i.id
--   where i.status <> 'void'
--   group by i.id, i.subtotal_amount having i.subtotal_amount <> sum(l.total_amount);
--
-- No outstanding balance disagrees with the payments recorded against it:
--   select i.id, i.outstanding_amount,
--          i.total_amount - coalesce(sum(p.amount) filter (where p.status = 'succeeded'), 0)
--   from public.invoices i left join public.payments p on p.invoice_id = i.id
--   where i.status <> 'void'
--   group by i.id, i.outstanding_amount, i.total_amount
--   having i.outstanding_amount <> i.total_amount
--          - coalesce(sum(p.amount) filter (where p.status = 'succeeded'), 0);
--
-- No flat was billed twice for one maintenance period:
--   select community_id, unit_id, billing_period_start, count(*)
--   from public.invoices where invoice_type = 'maintenance' and status <> 'void'
--   group by 1, 2, 3 having count(*) > 1;
--
-- No invoice belongs to a flat in another community (the composite FK should
-- make this impossible):
--   select i.id from public.invoices i
--   join public.apartments a on a.id = i.unit_id
--   where a.association_id <> i.community_id;
--
-- Running the billing twice for one period must report the second run entirely
-- as skipped (expect invoiced = 0):
--   select * from public.run_maintenance_billing('<community-uuid>'::uuid, '{}'::jsonb);
