-- ===========================================================================
-- Step 7 rebuilt: invoices, payments and billing settings, on the baseline.
--
-- This replaces the pre-baseline `0015_money.sql` (see `README.md`).
--
-- THE GAP THIS CLOSES IS MOSTLY COLUMNS, NOT TABLES
--
-- The baseline has `invoices`, `invoice_line_items`, `payments` and
-- `payment_events`, but models an invoice as five facts: who owes it, what
-- status it is in, when it is due, the total, and the timestamps. The
-- maintenance screen needs about thirty -- a number, a title, a type, a billing
-- period, tax, a running balance, the flat, the current resident, and how it was
-- eventually paid. Nearly everything below is `add column`.
--
-- `0018_settings_on_baseline.sql` already created `community_billing_settings`,
-- including the `next_invoice_seq` counter this file consumes. Only the RPC that
-- writes it was missing.
--
-- THE ONE RULE THIS FILE EXISTS TO ENFORCE
--
-- **No money is ever summed in Python.** `money_schemas.py` explains why amounts
-- cross the wire as floats; the consequence is that every total must be computed
-- in `numeric` by Postgres and read back. So `outstanding_amount` and
-- `amount_paid` are computed in the view, `total_amount` is derived from the
-- line items by the RPC, and no caller is trusted to add anything up.
--
-- WHY INVOICE LIABILITY MOVED
--
-- 0015 made an invoice liable BY UNIT. The baseline makes it liable by
-- `membership_id` -- a person, not a flat. Both are kept: `membership_id` stays
-- authoritative because it is the baseline's own foreign key and their code may
-- rely on it, and `unit_id` is added because the maintenance table is organised
-- by flat and a vacant flat still owes maintenance. The RPC resolves one from
-- the other where it can.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Invoice columns
--
-- `due_on` is a DATE beside the baseline's `due_at timestamptz`. A maintenance
-- bill is due on a day, not at an instant, and storing it as a timestamp makes
-- "is this overdue" depend on the reader's timezone. Both are written by the
-- RPC so their `due_at` readers keep working.
--
-- `invoice_number` is unique per community, not globally: two communities
-- numbering their invoices INV-0001 is correct behaviour, not a collision.
-- ---------------------------------------------------------------------------
alter table public.invoices
  add column if not exists unit_id               uuid references public.units(id) on delete set null,
  add column if not exists invoice_number        text,
  add column if not exists invoice_type          text not null default 'maintenance',
  add column if not exists title                 text,
  add column if not exists billing_period_start  date,
  add column if not exists billing_period_end    date,
  add column if not exists issued_on             date not null default current_date,
  add column if not exists due_on                date,
  add column if not exists subtotal_amount       numeric(12, 2) not null default 0,
  add column if not exists tax_amount            numeric(12, 2) not null default 0,
  add column if not exists currency_code         char(3) not null default 'INR',
  add column if not exists notes                 text;

alter table public.invoices alter column membership_id drop not null;

create unique index if not exists invoices_community_number_key
  on public.invoices (community_id, invoice_number)
  where invoice_number is not null;

create index if not exists invoices_unit_idx on public.invoices (unit_id);
create index if not exists invoices_due_idx  on public.invoices (community_id, due_on desc);

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'invoices_amounts_check'
  ) then
    alter table public.invoices
      add constraint invoices_amounts_check
      check (subtotal_amount >= 0 and tax_amount >= 0 and total_amount >= 0);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'invoices_period_check'
  ) then
    alter table public.invoices
      add constraint invoices_period_check
      check (billing_period_start is null
             or billing_period_end is null
             or billing_period_start <= billing_period_end);
  end if;

  -- An invoice must be liable to somebody or something. One of the two may be
  -- null -- a vacant flat has no membership, a resident may be billed with no
  -- flat -- but not both, or nobody owes it.
  if not exists (
    select 1 from pg_constraint where conname = 'invoices_liability_check'
  ) then
    alter table public.invoices
      add constraint invoices_liability_check
      check (membership_id is not null or unit_id is not null);
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Line items
--
-- `total_amount` is GENERATED, not written. It is the one number on an invoice
-- that must never disagree with its own inputs, and a generated column makes
-- that structurally impossible rather than merely tested.
--
-- The baseline's `amount` column stays and is kept equal to the computed total
-- by the RPC, so anything reading the baseline shape still sees the right
-- number.
-- ---------------------------------------------------------------------------
alter table public.invoice_line_items
  add column if not exists community_id uuid references public.communities(id) on delete cascade,
  add column if not exists quantity     numeric(12, 3) not null default 1,
  add column if not exists unit_amount  numeric(12, 2) not null default 0,
  add column if not exists sort_order   integer not null default 0;

-- Stated as a plain ALTER rather than hidden inside a DO block, so that a static
-- reader -- ours included -- can see the column exists without executing SQL.
alter table public.invoice_line_items
  add column if not exists total_amount numeric(12, 2)
  generated always as (round(quantity * unit_amount, 2)) stored;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'invoice_line_items_quantity_check'
  ) then
    alter table public.invoice_line_items
      add constraint invoice_line_items_quantity_check
      check (quantity > 0 and unit_amount >= 0);
  end if;
end $$;

create index if not exists invoice_line_items_invoice_idx
  on public.invoice_line_items (invoice_id, sort_order);

-- ---------------------------------------------------------------------------
-- 3. Payment columns
--
-- The baseline already carries `provider`, `provider_reference` and
-- `unique (community_id, idempotency_key)`, which is what makes
-- `record_payment` safely retryable. What it lacks is the human detail the
-- collection log shows: how it was paid, when, by whom, and who took it.
--
-- `paid_at` is separate from `created_at` on purpose. Cash handed over on
-- Friday and entered on Monday was received on Friday, and the collection log
-- is a record of when money arrived, not of when someone typed it in.
-- ---------------------------------------------------------------------------
alter table public.payments
  add column if not exists currency_code              char(3) not null default 'INR',
  add column if not exists payment_method             text,
  add column if not exists paid_at                    timestamptz not null default now(),
  add column if not exists notes                      text,
  add column if not exists payer_profile_id           uuid references public.profiles(id) on delete set null,
  add column if not exists received_by_membership_id  uuid references public.community_memberships(id) on delete set null;

create index if not exists payments_invoice_idx on public.payments (invoice_id, paid_at desc);

-- ---------------------------------------------------------------------------
-- 4. invoice_overview
--
-- Every figure the maintenance table shows, computed once.
--
-- `outstanding_amount` and `amount_paid` are aggregates over `payments`, not
-- stored columns, so they cannot drift from the payments that produced them.
-- Only `succeeded` payments count -- an initiated or failed one has not settled
-- anything.
--
-- `is_overdue` is derived on every read and never stored. A stored overdue flag
-- is true only until the next midnight, and then it is a lie until something
-- runs to correct it.
--
-- `resident_*` is the flat's CURRENT occupant, resolved at read time. The debt
-- belongs to the unit or the membership, not to whoever lives there today; they
-- are simply who the "Resident" column shows, and they are null for a vacant
-- flat -- which the frontend already renders as "Resident".
-- ---------------------------------------------------------------------------
drop view if exists public.invoice_overview;
create view public.invoice_overview
with (security_invoker = true) as
select
  i.id,
  i.community_id,
  i.unit_id,
  i.invoice_number,
  i.invoice_type,
  i.title,
  i.status::text                                       as status,
  i.billing_period_start,
  i.billing_period_end,
  i.issued_on,
  i.due_on,
  i.subtotal_amount,
  i.tax_amount,
  i.total_amount,
  greatest(i.total_amount - coalesce(p.amount_paid, 0), 0) as outstanding_amount,
  coalesce(p.amount_paid, 0)                           as amount_paid,
  i.currency_code,
  i.notes,
  i.created_at,
  i.updated_at,
  u.unit_code,
  b.name                                               as tower,
  res.membership_id                                    as resident_membership_id,
  res.profile_id                                       as resident_profile_id,
  res.full_name                                        as resident_name,
  p.paid_on,
  p.payment_method,
  (
    i.status <> 'void'
    and i.due_on is not null
    and i.due_on < current_date
    and i.total_amount - coalesce(p.amount_paid, 0) > 0
  )                                                    as is_overdue,
  lower(concat_ws(' ',
    i.title,
    i.invoice_number,
    u.unit_code,
    b.name,
    res.full_name
  ))                                                   as search_text
from public.invoices i
left join public.units u     on u.id = i.unit_id
left join public.buildings b on b.id = u.building_id
left join lateral (
  select
    sum(pay.amount)                                        as amount_paid,
    max(pay.paid_at)                                       as paid_on,
    (array_agg(pay.payment_method order by pay.paid_at desc)
       filter (where pay.payment_method is not null))[1]    as payment_method
    from public.payments pay
   where pay.invoice_id = i.id
     and pay.status = 'succeeded'
) p on true
left join lateral (
  select m.id as membership_id, m.profile_id, pr.full_name
    from public.unit_residencies r
    join public.community_memberships m on m.id = r.membership_id
    left join public.profiles pr on pr.id = m.profile_id
   where r.unit_id = i.unit_id
     and r.ended_at is null
   order by r.is_primary_contact desc, r.started_at desc
   limit 1
) res on true;

comment on view public.invoice_overview is
  'Invoices with their balance, flat, current resident and overdue flag. Runs as the caller (security_invoker), so RLS applies.';

-- ---------------------------------------------------------------------------
-- 5. payment_overview
-- ---------------------------------------------------------------------------
drop view if exists public.payment_overview;
create view public.payment_overview
with (security_invoker = true) as
select
  pay.id,
  pay.community_id,
  pay.invoice_id,
  pay.amount,
  pay.currency_code,
  pay.payment_method,
  pay.provider_reference,
  pay.status::text as status,
  pay.paid_at,
  pay.notes,
  pay.created_at,
  i.invoice_number,
  i.title          as invoice_title,
  i.unit_id,
  u.unit_code,
  pay.payer_profile_id,
  pr.full_name     as payer_name,
  pay.received_by_membership_id,
  lower(concat_ws(' ',
    i.invoice_number,
    i.title,
    u.unit_code,
    pr.full_name,
    pay.provider_reference
  ))               as search_text
from public.payments pay
left join public.invoices i on i.id = pay.invoice_id
left join public.units u    on u.id = i.unit_id
left join public.profiles pr on pr.id = pay.payer_profile_id;

comment on view public.payment_overview is
  'Recorded payments with the invoice, flat and payer each one settles.';

grant select on public.invoice_overview to authenticated;
grant select on public.payment_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 6. issue_invoice
--
-- Numbering takes a ROW LOCK on the settings row and consumes
-- `next_invoice_seq`. A sequence would be simpler but is global, and two
-- communities must not interleave their invoice numbers.
--
-- The flat is created on first reference. The product has never had a
-- flat-creation step -- `CreateInvoice` accepts a typed flat code -- so a code
-- that does not exist yet is normal input rather than an error.
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
  v_id           uuid;
  v_unit_id      uuid := nullif(p_payload ->> 'unit_id', '')::uuid;
  v_unit_code    text := nullif(btrim(coalesce(p_payload ->> 'unit_code', '')), '');
  v_prefix       text;
  v_seq          bigint;
  v_number       text;
  v_tax_percent  numeric(5, 2);
  v_subtotal     numeric(12, 2);
  v_tax          numeric(12, 2);
  v_membership   uuid;
  v_item         jsonb;
  v_sort         integer := 0;
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may issue an invoice.'
      using errcode = '42501';
  end if;

  if p_payload -> 'line_items' is null
     or jsonb_array_length(p_payload -> 'line_items') = 0 then
    raise exception 'An invoice needs at least one line item.' using errcode = '23514';
  end if;

  -- Resolve the flat, creating it if the code is new to us.
  if v_unit_id is null and v_unit_code is not null then
    select id into v_unit_id
      from public.units
     where community_id = p_community_id
       and upper(unit_code) = upper(v_unit_code)
     limit 1;

    if v_unit_id is null then
      insert into public.units (community_id, unit_code)
      values (p_community_id, v_unit_code)
      returning id into v_unit_id;
    end if;
  end if;

  if v_unit_id is not null then
    select m.id into v_membership
      from public.unit_residencies r
      join public.community_memberships m on m.id = r.membership_id
     where r.unit_id = v_unit_id
       and r.ended_at is null
     order by r.is_primary_contact desc, r.started_at desc
     limit 1;
  end if;

  if v_unit_id is null and v_membership is null then
    raise exception 'An invoice needs a flat or a member to be liable for it.'
      using errcode = '23514';
  end if;

  -- Numbering, under a lock so two concurrent issues cannot take the same seq.
  insert into public.community_billing_settings (community_id)
  values (p_community_id)
  on conflict (community_id) do nothing;

  select invoice_number_prefix, next_invoice_seq, default_tax_percent
    into v_prefix, v_seq, v_tax_percent
    from public.community_billing_settings
   where community_id = p_community_id
     for update;

  update public.community_billing_settings
     set next_invoice_seq = next_invoice_seq + 1,
         updated_at = now()
   where community_id = p_community_id;

  v_number := v_prefix || '-' || lpad(v_seq::text, 5, '0');

  if p_payload ? 'tax_percent' then
    v_tax_percent := (p_payload ->> 'tax_percent')::numeric;
  end if;

  insert into public.invoices (
    community_id, unit_id, membership_id, invoice_number, invoice_type, title,
    status, billing_period_start, billing_period_end, issued_on, due_on, due_at,
    currency_code, notes, subtotal_amount, tax_amount, total_amount
  )
  values (
    p_community_id,
    v_unit_id,
    v_membership,
    v_number,
    coalesce(nullif(btrim(coalesce(p_payload ->> 'invoice_type', '')), ''), 'maintenance'),
    btrim(coalesce(p_payload ->> 'title', 'Invoice')),
    'issued',
    (nullif(p_payload ->> 'billing_period_start', ''))::date,
    (nullif(p_payload ->> 'billing_period_end', ''))::date,
    coalesce((nullif(p_payload ->> 'issued_on', ''))::date, current_date),
    (nullif(p_payload ->> 'due_on', ''))::date,
    (nullif(p_payload ->> 'due_on', ''))::timestamptz,
    'INR',
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), ''),
    0, 0, 0
  )
  returning id into v_id;

  for v_item in select * from jsonb_array_elements(p_payload -> 'line_items') loop
    insert into public.invoice_line_items (
      invoice_id, community_id, description, quantity, unit_amount, amount, sort_order
    )
    values (
      v_id,
      p_community_id,
      btrim(coalesce(v_item ->> 'description', '')),
      coalesce((v_item ->> 'quantity')::numeric, 1),
      coalesce((v_item ->> 'unit_amount')::numeric, 0),
      round(coalesce((v_item ->> 'quantity')::numeric, 1)
            * coalesce((v_item ->> 'unit_amount')::numeric, 0), 2),
      v_sort
    );
    v_sort := v_sort + 1;
  end loop;

  -- Totals come back OUT of the database rather than being trusted from the
  -- caller: the line items are the source of truth for what the invoice is worth.
  select coalesce(sum(total_amount), 0) into v_subtotal
    from public.invoice_line_items where invoice_id = v_id;

  v_tax := round(v_subtotal * coalesce(v_tax_percent, 0) / 100, 2);

  update public.invoices
     set subtotal_amount = v_subtotal,
         tax_amount      = v_tax,
         total_amount    = v_subtotal + v_tax,
         updated_at      = now()
   where id = v_id;

  return v_id;
end $$;

-- ---------------------------------------------------------------------------
-- 7. record_payment
--
-- Idempotent on `provider_reference`, which is written to the baseline's
-- `idempotency_key` so that `unique (community_id, idempotency_key)` does the
-- enforcing. A gateway retrying its webhook, or a resident double-tapping Pay,
-- must not settle a bill twice -- so a repeat call RETURNS THE EXISTING PAYMENT
-- rather than raising, and the caller cannot tell the difference.
--
-- The invoice status is recomputed from the payments, never assumed: paid when
-- the balance reaches zero, partially_paid while something is still owed.
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
  v_community_id uuid;
  v_total        numeric(12, 2);
  v_reference    text := nullif(btrim(coalesce(p_payload ->> 'provider_reference', '')), '');
  v_amount       numeric(12, 2) := (p_payload ->> 'amount')::numeric;
  v_id           uuid;
  v_paid         numeric(12, 2);
begin
  select community_id, total_amount into v_community_id, v_total
    from public.invoices where id = p_invoice_id;

  if v_community_id is null then
    raise exception 'Invoice not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin of this community may record a payment.'
      using errcode = '42501';
  end if;

  if v_amount is null or v_amount <= 0 then
    raise exception 'A payment must be for a positive amount.' using errcode = '23514';
  end if;

  -- The idempotent path, before anything is written.
  if v_reference is not null then
    select id into v_id
      from public.payments
     where community_id = v_community_id
       and idempotency_key = v_reference
     limit 1;

    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.payments (
    community_id, invoice_id, provider, provider_reference, idempotency_key,
    amount, currency_code, payment_method, status, paid_at, notes,
    payer_profile_id
  )
  values (
    v_community_id,
    p_invoice_id,
    'offline',
    v_reference,
    v_reference,
    v_amount,
    'INR',
    nullif(btrim(coalesce(p_payload ->> 'payment_method', '')), ''),
    'succeeded',
    coalesce((nullif(p_payload ->> 'paid_at', ''))::timestamptz, now()),
    nullif(btrim(coalesce(p_payload ->> 'notes', '')), ''),
    nullif(p_payload ->> 'payer_profile_id', '')::uuid
  )
  returning id into v_id;

  insert into public.payment_events (payment_id, event_type, payload)
  values (v_id, 'recorded', jsonb_build_object('amount', v_amount));

  select coalesce(sum(amount), 0) into v_paid
    from public.payments
   where invoice_id = p_invoice_id and status = 'succeeded';

  update public.invoices
     set status = case
                    when v_paid >= v_total then 'paid'::public.invoice_status
                    when v_paid > 0        then 'partially_paid'::public.invoice_status
                    else status
                  end,
         updated_at = now()
   where id = p_invoice_id;

  return v_id;
end $$;

-- ---------------------------------------------------------------------------
-- 8. update_billing_settings
--
-- Creates the row on first use, so a community that has never opened the
-- Settings screen does not 404 on its first save.
--
-- The two cross-field rules are enforced HERE and raise `23514` rather than
-- being silently ignored: switching on automated billing with no maintenance
-- amount, or late fees with no fee amount, configures nothing. The frontend's
-- current bug is that such a toggle springs back on the next read with no
-- explanation; a 409 tells the admin what is missing.
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
declare
  v_row public.community_billing_settings%rowtype;
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an admin of this community may change billing settings.'
      using errcode = '42501';
  end if;

  insert into public.community_billing_settings (community_id)
  values (p_community_id)
  on conflict (community_id) do nothing;

  update public.community_billing_settings
     set currency_code              = case when p_patch ? 'currency_code'              then (p_patch ->> 'currency_code')::char(3)          else currency_code              end,
         invoice_number_prefix      = case when p_patch ? 'invoice_number_prefix'      then p_patch ->> 'invoice_number_prefix'             else invoice_number_prefix      end,
         default_maintenance_amount = case when p_patch ? 'default_maintenance_amount' then (nullif(p_patch ->> 'default_maintenance_amount', ''))::numeric else default_maintenance_amount end,
         maintenance_due_day        = case when p_patch ? 'maintenance_due_day'        then (p_patch ->> 'maintenance_due_day')::smallint   else maintenance_due_day        end,
         default_tax_percent        = case when p_patch ? 'default_tax_percent'        then (p_patch ->> 'default_tax_percent')::numeric    else default_tax_percent        end,
         auto_billing_enabled       = case when p_patch ? 'auto_billing_enabled'       then (p_patch ->> 'auto_billing_enabled')::boolean   else auto_billing_enabled       end,
         auto_billing_day           = case when p_patch ? 'auto_billing_day'           then (p_patch ->> 'auto_billing_day')::smallint      else auto_billing_day           end,
         late_fee_enabled           = case when p_patch ? 'late_fee_enabled'           then (p_patch ->> 'late_fee_enabled')::boolean       else late_fee_enabled           end,
         late_fee_amount            = case when p_patch ? 'late_fee_amount'            then (nullif(p_patch ->> 'late_fee_amount', ''))::numeric else late_fee_amount       end,
         late_fee_grace_days        = case when p_patch ? 'late_fee_grace_days'        then (p_patch ->> 'late_fee_grace_days')::smallint   else late_fee_grace_days        end,
         late_fee_period            = case when p_patch ? 'late_fee_period'            then p_patch ->> 'late_fee_period'                   else late_fee_period            end,
         version                    = version + 1,
         updated_at                 = now()
   where community_id = p_community_id
  returning * into v_row;

  if v_row.auto_billing_enabled and v_row.default_maintenance_amount is null then
    raise exception 'Automated billing needs a default maintenance amount.'
      using errcode = '23514';
  end if;

  if v_row.late_fee_enabled
     and (v_row.late_fee_amount is null or v_row.late_fee_amount <= 0) then
    raise exception 'Late fees need a fee amount above zero.'
      using errcode = '23514';
  end if;
end $$;

grant execute on function public.issue_invoice(uuid, jsonb)            to authenticated;
grant execute on function public.record_payment(uuid, jsonb)           to authenticated;
grant execute on function public.update_billing_settings(uuid, jsonb)  to authenticated;

-- ---------------------------------------------------------------------------
-- 9. Row-level security
--
-- A resident may see their own invoices and the payments against them; an admin
-- sees the community's. Writes are admin-only and go through the RPCs above.
--
-- The resident test goes through `unit_residencies` as well as `membership_id`,
-- because an invoice raised against a vacant flat later becomes the debt of
-- whoever moves in, and they must be able to see what they are being asked to
-- pay.
-- ---------------------------------------------------------------------------
alter table public.invoices            enable row level security;
alter table public.invoice_line_items  enable row level security;
alter table public.payments            enable row level security;
alter table public.payment_events      enable row level security;

drop policy if exists invoices_read on public.invoices;
create policy invoices_read on public.invoices
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or exists (
      select 1 from public.community_memberships m
       where m.id = invoices.membership_id
         and m.profile_id = auth.uid()
    )
    or exists (
      select 1 from public.unit_residencies r
       join public.community_memberships m on m.id = r.membership_id
       where r.unit_id = invoices.unit_id
         and r.ended_at is null
         and m.profile_id = auth.uid()
    )
  );

drop policy if exists invoices_admin_write on public.invoices;
create policy invoices_admin_write on public.invoices
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

drop policy if exists invoice_line_items_read on public.invoice_line_items;
create policy invoice_line_items_read on public.invoice_line_items
  for select to authenticated
  using (exists (
    select 1 from public.invoices i
     where i.id = invoice_id
       and (
         public.is_community_admin(i.community_id)
         or exists (
           select 1 from public.community_memberships m
            where m.id = i.membership_id and m.profile_id = auth.uid()
         )
       )
  ));

drop policy if exists payments_read on public.payments;
create policy payments_read on public.payments
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or payer_profile_id = auth.uid()
    or exists (
      select 1 from public.invoices i
       join public.community_memberships m on m.id = i.membership_id
       where i.id = payments.invoice_id and m.profile_id = auth.uid()
    )
  );

drop policy if exists payment_events_read on public.payment_events;
create policy payment_events_read on public.payment_events
  for select to authenticated
  using (exists (
    select 1 from public.payments p
     where p.id = payment_id
       and public.is_community_admin(p.community_id)
  ));

-- ---------------------------------------------------------------------------
-- 10. SSE outbox
-- ---------------------------------------------------------------------------
drop trigger if exists invoices_sse on public.invoices;
create trigger invoices_sse
  after insert or update or delete on public.invoices
  for each row execute function public.emit_dashboard_sse_event();

drop trigger if exists payments_sse on public.payments;
create trigger payments_sse
  after insert or update or delete on public.payments
  for each row execute function public.emit_dashboard_sse_event();
