-- The resident's money and the resident's home: their invoices, the simulated
-- settlement that pays one, the same settlement for an amenity booking, the
-- notice board, the numbers registered to their flat, and a contact directory
-- that is currently hard-coded in a JSX file.
--
-- docs/design/RESIDENT_BACKEND_DESIGN.md §5.5, §5.6, §6, §7, §11, §9 step 6.
--
-- WHY THIS FILE IS 0033
--
-- Above `0030`, because three of its functions call `notify_member`. Same
-- constraint as `0031` and `0032` and the same failure mode if ignored: a
-- plpgsql body is not resolved against the catalogue until it executes, so a
-- lower number would apply cleanly and fail at the first payment.
--
-- WHAT WAS ALREADY HERE, AND IT IS A LOT
--
-- `invoices`, `invoice_line_items`, `payments` and `payment_events` are all in
-- the baseline, and `0021` gave them everything the admin's collection log
-- needs -- `invoice_overview` with its aggregates, `record_payment` with its
-- idempotency, and RLS that already lets a resident read their own invoices.
--
-- **What is missing is not storage. It is a writer a resident is allowed to
-- call.** `record_payment` refuses anyone who is not an admin, by design (§5.5):
-- an admin records a payment that happened elsewhere, a resident initiates one.
-- This file adds the second verb, not a second ledger.
--
-- THE SIMULATOR IS NOT IN THIS FILE, AND THAT IS THE POINT
--
-- §11.6: the gateway is one pure Python function, and the RPC below is what a
-- real gateway would call *unchanged*. So `settle_resident_payment` takes an
-- outcome -- `succeeded` or `failed`, with a reason -- and never decides one. It
-- validates the business rules a gateway has no opinion about (is this your
-- invoice, is it already paid, is the amount the balance), writes the payment,
-- appends the event, recomputes the invoice from `succeeded` rows only, and
-- notifies. Swapping the simulator for Razorpay changes one Python module and
-- nothing here.
--
-- **`provider = 'simulator'`.** Written on every row this file settles, and it
-- is the single most important string in the migration. A demo database becomes
-- a staging database becomes, occasionally, something a person reconciles
-- against a bank statement. If simulated money is recorded as `offline` -- which
-- is what `record_payment` writes -- then on the day a real gateway arrives,
-- nobody can ever separate the money that moved from the money that did not.
-- That is not a recoverable mistake. The information was never recorded.
--
-- WHAT IS NEVER STORED
--
-- No card number, no CVV, no expiry, anywhere -- not in `payments`, not in
-- `payment_events`, not in an error payload (§11.3). The RPC below cannot store
-- one because it is never given one: the service validates the instrument in a
-- pure function and passes on a masked label. `•••• 4242` is a receipt line,
-- not a credential.
--
-- FIFTH INSTANCE OF THE RLS TIMING RULE
--
-- `notices`, `unit_residencies` and `departments` have had no row security since
-- the baseline. Every authenticated user in the project can read every notice,
-- every residency and every department -- who lives in which flat being the
-- worst of the three. Tolerable only while those tables were served exclusively
-- through admin-guarded endpoints; this migration is what puts them behind
-- endpoints a resident calls, so the policies land in the same file. `0028`,
-- `0030`, `0031`, `0032`, and now this one.

-- ---------------------------------------------------------------------------
-- 1. What a payment has to say when it fails
--
-- `record_payment` writes `succeeded` and nothing else, because an admin only
-- records money that already arrived. A gateway declines, and a decline that
-- says only "failed" is a row nobody can act on: the resident needs to be told
-- to try another card, and only the reason distinguishes that from "try again
-- in a minute".
--
-- `failure_code` is a stable identifier, never prose -- `card_declined`, not
-- "Your card was declined." The message is the client's to phrase and the
-- client's to translate.
--
-- The CHECK is what keeps the column honest: a code on a succeeded payment is a
-- contradiction, and one on an `initiated` payment is a guess about an outcome
-- that has not happened.
-- ---------------------------------------------------------------------------

alter table public.payments
  add column if not exists failure_code     text,
  add column if not exists instrument_label text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'payments_failure_code_check'
  ) then
    alter table public.payments
      add constraint payments_failure_code_check
      check (failure_code is null or status = 'failed');
  end if;
end $$;

comment on column public.payments.failure_code is
  'Stable decline reason, null unless status = failed. Never prose -- the wording is the client''s.';
comment on column public.payments.instrument_label is
  'Masked display line for the receipt. NEVER a PAN, a CVV or an expiry -- see §11.3.';

-- ---------------------------------------------------------------------------
-- 2. Is this invoice the caller's?
--
-- Lifted verbatim from `0021`'s `invoices_read` policy, because the write path
-- and the read path disagreeing about whose invoice this is would be the worst
-- possible bug here: a resident able to pay a bill they cannot see, or unable to
-- pay one they can.
--
-- Two ways in, and the second is not redundant. An invoice raised against a
-- vacant flat carries a `unit_id` and no `membership_id`; when somebody moves
-- in, that debt becomes theirs. They must be able to see it and settle it, and
-- they have no membership on the row to match.
-- ---------------------------------------------------------------------------

create or replace function public.is_own_invoice(p_invoice_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.invoices i
     where i.id = p_invoice_id
       and (
         exists (
           select 1 from public.community_memberships m
            where m.id = i.membership_id
              and m.profile_id = auth.uid()
         )
         or exists (
           select 1 from public.unit_residencies r
             join public.community_memberships m on m.id = r.membership_id
            where r.unit_id = i.unit_id
              and r.ended_at is null
              and m.profile_id = auth.uid()
         )
       )
  );
$$;

comment on function public.is_own_invoice(uuid) is
  'True when the caller is liable for this invoice, by membership or by current residency of the billed unit. Mirrors 0021''s read policy exactly.';

grant execute on function public.is_own_invoice(uuid) to authenticated;

-- `0021` gave `invoices_read` both routes and `invoice_line_items_read` only
-- one, so a resident who inherited a vacant flat's bill could see the total and
-- not a single line of what it was for. Restated through the function, which is
-- why the function exists.
drop policy if exists invoice_line_items_read on public.invoice_line_items;
create policy invoice_line_items_read on public.invoice_line_items
  for select to authenticated
  using (exists (
    select 1 from public.invoices i
     where i.id = invoice_id
       and (public.is_community_admin(i.community_id) or public.is_own_invoice(i.id))
  ));

-- Same omission on payments: an admin could see the payment history of an
-- invoice, and the person who paid it could see only the rows carrying their own
-- profile id. A payment made against the flat before they moved in is part of
-- what they owe.
drop policy if exists payments_read on public.payments;
create policy payments_read on public.payments
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or payer_profile_id = auth.uid()
    or (invoice_id is not null and public.is_own_invoice(invoice_id))
  );

-- ---------------------------------------------------------------------------
-- 3. resident_invoice_overview
--
-- `invoice_overview` (`0021`) already computes every figure, but it is the
-- admin's projection: it carries the resident's name, their profile id and a
-- search blob, because the collection log is a table of *other people's* debts.
-- A resident reading their own bill needs none of that and should not receive
-- their neighbour's column list by inheritance.
--
-- `status` is the wire word, not the enum. Six stored statuses collapse to the
-- two the screen has -- `Payments.jsx` filters on `'Unpaid'` and `'Paid'` and
-- has no third branch -- so `partially_paid` and `overdue` read as `Unpaid`,
-- which is what they are to the person who owes the money. `stored_status` is
-- beside it for anything that needs the real one, exactly as
-- `amenity_booking_overview` does it.
--
-- `is_payable` is computed here rather than inferred from the status by each
-- caller. It is the precondition the RPC enforces, and a screen that draws a Pay
-- button from a different rule than the one the write path applies is a screen
-- with a button that fails.
--
-- **`is_mine` is `is_own_invoice`, not a second opinion.** §2 above says that the
-- read path and the write path disagreeing about whose invoice this is would be
-- the worst possible bug in this file -- "a resident able to pay a bill they
-- cannot see". Filtering the list on `membership_id` produces exactly that: an
-- invoice raised against a vacant flat carries a `unit_id` and a null
-- `membership_id` (`0021` drops the NOT NULL), so it is payable through the
-- second branch of `is_own_invoice` and matches no membership filter. The list
-- calls the same function the RPC does, which costs two EXISTS per row on a list
-- of tens and buys the guarantee that the two can never drift.
--
-- **Drafts are not in here at all.** A draft is a bill the admin has not issued;
-- it has no number, no promise and nothing to pay. It was reaching the resident
-- through `status = 'Unpaid'` -- an amount owed on a bill nobody had sent.
-- ---------------------------------------------------------------------------

drop view if exists public.resident_invoice_overview;
create view public.resident_invoice_overview
with (security_invoker = true) as
select
  i.id,
  i.community_id,
  i.membership_id,
  i.unit_id,
  i.invoice_number,
  i.invoice_type,
  coalesce(nullif(btrim(i.title), ''), 'Maintenance')      as title,
  case i.status
    when 'paid' then 'Paid'
    when 'void' then 'Cancelled'
    else 'Unpaid'
  end                                                      as status,
  i.status::text                                           as stored_status,
  i.issued_on,
  i.due_on,
  i.total_amount,
  coalesce(p.amount_paid, 0)                               as amount_paid,
  greatest(i.total_amount - coalesce(p.amount_paid, 0), 0) as outstanding_amount,
  i.currency_code,
  i.notes,
  i.created_at,
  p.paid_at,
  p.payment_method,
  p.instrument_label,
  (
    i.status <> 'void'
    and i.due_on is not null
    and i.due_on < current_date
    and i.total_amount - coalesce(p.amount_paid, 0) > 0
  )                                                        as is_overdue,
  (
    i.status not in ('paid', 'void', 'draft')
    and i.total_amount - coalesce(p.amount_paid, 0) > 0
  )                                                        as is_payable,
  public.is_own_invoice(i.id)                              as is_mine
from public.invoices i
left join lateral (
  select
    sum(pay.amount)                          as amount_paid,
    max(pay.paid_at)                         as paid_at,
    (array_agg(pay.payment_method  order by pay.paid_at desc))[1] as payment_method,
    (array_agg(pay.instrument_label order by pay.paid_at desc))[1] as instrument_label
    from public.payments pay
   where pay.invoice_id = i.id
     and pay.status = 'succeeded'
) p on true
where i.status <> 'draft';

comment on view public.resident_invoice_overview is
  'A resident''s own bills. Wire statuses, the outstanding balance, and the payability rule the settlement RPC enforces.';

grant select on public.resident_invoice_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 4. settle_resident_payment
--
-- The seam (§11.6). Takes an outcome; never produces one.
--
-- Order matters and it is deliberate. The **idempotent path runs first**, before
-- any validation, because a retry of a payment that already settled must return
-- the same row even though the invoice is now `paid` and would fail the
-- payability check. Getting that backwards turns a double-tap into an error
-- message about a bill the resident has already paid.
--
-- Then the business rules, which §11.2 requires be enforced here rather than in
-- the service: your invoice, not already settled, and the full outstanding
-- balance. A partial payment is a policy question nobody has answered, and
-- accepting one silently would leave a resident believing they had paid.
--
-- **A declined payment is still written.** That is the whole difference between
-- this and `record_payment`: `failed` rows are a record that the resident tried,
-- they are what a support conversation is reconstructed from, and they never
-- enter a balance because every recomputation below sums `succeeded` only.
--
-- **It returns the payment, not an id.** An id makes the caller describe an
-- outcome it has to have guessed, and on the replay path its guess is wrong: the
-- stored row is the *first* attempt's, so a retry judged against a different card
-- would be reported with the new verdict over the old record -- a response saying
-- `failed` beside a `settledStatus` of `Paid`. What comes back is what is in the
-- table.
-- ---------------------------------------------------------------------------

-- One shape, built once. Every path that has to describe a payment -- the replay,
-- the fresh settlement, and the pre-flight lookup below -- reads it from the row
-- rather than assembling its own version of the same five fields.
create or replace function public.payment_as_outcome(p_payment_id uuid)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
           'payment_id',       p.id,
           'status',           p.status::text,
           'failure_code',     p.failure_code,
           'instrument_label', p.instrument_label,
           'amount',           p.amount
         )
    from public.payments p
   where p.id = p_payment_id;
$$;

comment on function public.payment_as_outcome(uuid) is
  'The five facts a client needs about a settled payment, read from the row rather than assumed by the caller.';

-- The pre-flight lookup. Its reason for existing is on the Python side: the
-- service must be able to recognise a replay **before** it calls the gateway.
-- With a pure simulator that is merely tidy; with a real provider behind the same
-- seam, calling first and checking afterwards is a double charge on every
-- double-tap, which is the one failure an idempotency key exists to prevent.
create or replace function public.find_resident_payment(
  p_invoice_id uuid,
  p_key        text
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_key          text := nullif(btrim(coalesce(p_key, '')), '');
  v_id           uuid;
  v_target       uuid;
begin
  if v_key is null then
    return null;
  end if;

  select i.community_id into v_community_id
    from public.invoices i where i.id = p_invoice_id;

  if v_community_id is null or not public.is_own_invoice(p_invoice_id) then
    return null;
  end if;

  select p.id, p.invoice_id into v_id, v_target
    from public.payments p
   where p.community_id = v_community_id
     and p.idempotency_key = v_key
   limit 1;

  if v_id is null then
    return null;
  end if;

  -- A key that already belongs to a different bill is a client bug, and the
  -- dangerous answer is the friendly one: hand back the other invoice's payment
  -- and this invoice reports `succeeded` while remaining entirely unpaid.
  if v_target is distinct from p_invoice_id then
    raise exception 'That idempotency key already settled a different invoice.'
      using errcode = 'HB409';
  end if;

  return public.payment_as_outcome(v_id);
end;
$$;

comment on function public.find_resident_payment(uuid, text) is
  'Look up a prior attempt by idempotency key, so the caller can recognise a replay before it calls a gateway.';

grant execute on function public.find_resident_payment(uuid, text) to authenticated;

drop function if exists public.settle_resident_payment(uuid, jsonb);
create or replace function public.settle_resident_payment(
  p_invoice_id uuid,
  p_payload    jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_membership   uuid;
  v_status       public.invoice_status;
  v_total        numeric(12, 2);
  v_key          text := nullif(btrim(coalesce(p_payload ->> 'idempotency_key', '')), '');
  v_outcome      text := lower(coalesce(p_payload ->> 'status', ''));
  v_amount       numeric(12, 2) := (p_payload ->> 'amount')::numeric;
  v_paid         numeric(12, 2);
  v_outstanding  numeric(12, 2);
  v_id           uuid;
  v_target       uuid;
begin
  select i.community_id, i.membership_id, i.status, i.total_amount
    into v_community_id, v_membership, v_status, v_total
    from public.invoices i where i.id = p_invoice_id;

  if v_community_id is null then
    raise exception 'Invoice not found.' using errcode = 'P0002';
  end if;

  -- Before the ownership check, deliberately: a repeat is answered with the row
  -- it already produced, and a caller replaying their own key has already
  -- passed every check below once. `find_resident_payment` does this too and
  -- normally gets there first; this copy is what closes the window between the
  -- two calls, when the same key arrives twice at once.
  if v_key is not null then
    select id, invoice_id into v_id, v_target
      from public.payments
     where community_id = v_community_id
       and idempotency_key = v_key
     limit 1;

    if v_id is not null then
      if v_target is distinct from p_invoice_id then
        raise exception 'That idempotency key already settled a different invoice.'
          using errcode = 'HB409';
      end if;
      return public.payment_as_outcome(v_id);
    end if;
  end if;

  if not public.is_own_invoice(p_invoice_id) then
    raise exception 'You may only pay your own invoice.' using errcode = '42501';
  end if;

  if v_key is null then
    raise exception 'A payment needs an idempotency key.' using errcode = '22004';
  end if;

  if v_outcome not in ('succeeded', 'failed') then
    raise exception 'A settlement must be succeeded or failed.' using errcode = '22P02';
  end if;

  if v_status in ('paid', 'void') then
    raise exception 'This invoice has already been settled.' using errcode = 'HB409';
  end if;

  select coalesce(sum(amount), 0) into v_paid
    from public.payments
   where invoice_id = p_invoice_id and status = 'succeeded';

  v_outstanding := greatest(v_total - v_paid, 0);

  if v_outstanding <= 0 then
    raise exception 'This invoice has already been settled.' using errcode = 'HB409';
  end if;

  -- Compared to the balance the database computed, never to a number the client
  -- sent alongside it. The amount is in the request so the caller can be told
  -- they are out of date, not so they can choose.
  if v_amount is null or v_amount <> v_outstanding then
    raise exception 'A payment must settle the full outstanding balance.'
      using errcode = '23514';
  end if;

  insert into public.payments (
    community_id, invoice_id, provider, provider_reference, idempotency_key,
    amount, currency_code, payment_method, instrument_label, status,
    failure_code, paid_at, payer_profile_id
  )
  values (
    v_community_id,
    p_invoice_id,
    'simulator',
    v_key,
    v_key,
    v_amount,
    'INR',
    nullif(btrim(coalesce(p_payload ->> 'payment_method', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'instrument_label', '')), ''),
    v_outcome::public.payment_status,
    case when v_outcome = 'failed'
         then nullif(btrim(coalesce(p_payload ->> 'failure_code', '')), '')
         else null end,
    now(),
    auth.uid()
  )
  returning id into v_id;

  -- Two rows, not one. A real integration's audit trail is `initiated` then
  -- `authorized` or `declined`, arriving at different times and sometimes from
  -- different directions; writing only the outcome would make this table the
  -- wrong shape for the thing it exists to become.
  insert into public.payment_events (payment_id, event_type, payload)
  values
    (v_id, 'initiated', jsonb_build_object('amount', v_amount, 'provider', 'simulator')),
    (
      v_id,
      case when v_outcome = 'succeeded' then 'simulated_authorized'
           else 'simulated_declined' end,
      jsonb_build_object(
        'amount', v_amount,
        'failure_code', p_payload ->> 'failure_code'
      )
    );

  if v_outcome = 'succeeded' then
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
  end if;

  -- The resident is told either way. A decline they are not told about is a
  -- resident who believes they have paid, which is the failure US-2.12 names on
  -- the booking side and is no better here.
  if v_membership is not null then
    perform public.notify_member(
      v_membership,
      case when v_outcome = 'succeeded' then 'payment.succeeded' else 'payment.failed' end,
      jsonb_build_object(
        'title', case when v_outcome = 'succeeded'
                      then 'Payment received' else 'Payment failed' end,
        'body',  case when v_outcome = 'succeeded'
                      then 'Your maintenance bill has been paid.'
                      else 'Your payment did not go through. No money has been taken.' end,
        'url',   '/resident/payments',
        'invoice_id', p_invoice_id,
        'payment_id', v_id,
        'failure_code', p_payload ->> 'failure_code'
      )
    );
  end if;

  return public.payment_as_outcome(v_id);
end;
$$;

comment on function public.settle_resident_payment(uuid, jsonb) is
  'Record a resident-initiated payment outcome against their own invoice. Takes the outcome, never decides it -- the seam a real gateway slots into.';

grant execute on function public.settle_resident_payment(uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- 5. The resident's own bookings, and what they owe on one
--
-- `amenity_booking_charges` and `amenity_financial_events` are admin-only reads
-- (`0023` §15), under the reasoning that the ledger "records what residents were
-- charged and refunded, which is not a community-wide fact". Correct about the
-- community and wrong about the resident: the one person who is entitled to know
-- what a booking costs is the person being asked to pay it.
--
-- Both policies gain an own-booking clause. Neither becomes community-visible.
-- ---------------------------------------------------------------------------

-- A declined attempt has to be recorded somewhere, and `amenity_financial_events`
-- is the only ledger a booking has. Its CHECK allowed four event types, none of
-- which means "this did not go through": writing a decline as a `charge` would
-- put a phantom line in the admin's ledger, and writing it as a `payment` of
-- zero would put a paid-in-full booking in front of a resident who paid nothing.
--
-- So the vocabulary gains the word it was missing. Every aggregate in
-- `amenity_ledger_overview` is `filter (where event_type = ...)`, so an
-- unrecognised type is invisible to all of them -- the new row records the
-- attempt for its full amount and counts towards nothing.
-- And the receipt line, for the same reason §1 puts one on `payments`: a resident
-- who paid for the clubhouse is entitled to be told what they paid with, and a
-- replayed attempt cannot be described from a row that never recorded it. Masked
-- display text only -- never a PAN, a CVV or an expiry.
alter table public.amenity_financial_events
  add column if not exists instrument_label text;

comment on column public.amenity_financial_events.instrument_label is
  'Masked display line for the receipt. NEVER a PAN, a CVV or an expiry -- see §11.3.';

do $$
begin
  if exists (
    select 1 from pg_constraint
     where conname = 'amenity_financial_events_event_type_check'
  ) then
    alter table public.amenity_financial_events
      drop constraint amenity_financial_events_event_type_check;
  end if;

  alter table public.amenity_financial_events
    add constraint amenity_financial_events_event_type_check
    check (event_type in ('payment', 'refund', 'damage_deduction', 'charge',
                          'payment_failed'));
end $$;

create or replace function public.is_own_booking(p_booking_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.amenity_bookings bk
      join public.community_memberships m on m.id = bk.booked_by_membership_id
     where bk.id = p_booking_id
       and m.profile_id = auth.uid()
  );
$$;

comment on function public.is_own_booking(uuid) is
  'True when the caller raised this amenity booking. Used by the resident ledger policies and the settlement RPC.';

grant execute on function public.is_own_booking(uuid) to authenticated;

drop policy if exists amenity_booking_charges_read on public.amenity_booking_charges;
create policy amenity_booking_charges_read on public.amenity_booking_charges
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or public.is_own_booking(booking_occurrence_id)
  );

drop policy if exists amenity_financial_events_read on public.amenity_financial_events;
create policy amenity_financial_events_read on public.amenity_financial_events
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or exists (
      select 1 from public.amenity_booking_charges ch
       where ch.id = booking_charge_id
         and public.is_own_booking(ch.booking_occurrence_id)
    )
  );

-- The arithmetic is `amenity_ledger_overview`'s, deliberately identical: charges
-- summed, payments summed, the difference outstanding. Two views computing one
-- balance differently is how a resident and an admin end up looking at the same
-- booking and disagreeing about whether it is paid.
drop view if exists public.resident_booking_overview;
create view public.resident_booking_overview
with (security_invoker = true) as
select
  bk.id,
  bk.community_id,
  coalesce(bk.booking_group_id, bk.id)                       as booking_series_id,
  bk.booked_by_membership_id                                 as requested_by_membership_id,
  bk.amenity_id,
  am.name                                                    as amenity_name,
  bk.title,
  bk.starts_at,
  bk.ends_at,
  (bk.starts_at at time zone coalesce(cs.timezone, c.timezone, 'Asia/Kolkata'))::date
                                                             as booking_date,
  case bk.status
    when 'requested' then 'Pending'
    when 'approved'  then 'Approved'
    when 'rejected'  then 'Rejected'
    when 'cancelled' then 'Cancelled'
    when 'completed' then 'Completed'
    when 'no_show'   then 'No Show'
    else initcap(bk.status::text)
  end                                                        as status,
  bk.status::text                                            as stored_status,
  bk.guest_count,
  bk.is_private,
  bk.notes,
  bk.cancelled_at,
  bk.cancellation_reason,
  bk.rejection_reason,
  bk.created_at,
  coalesce(ch.total_amount, 0)                               as total_amount,
  coalesce(ev.amount_paid, 0)                                as amount_paid,
  greatest(coalesce(ch.total_amount, 0) - coalesce(ev.amount_paid, 0), 0)
                                                             as outstanding_amount,
  (
    bk.status in ('requested', 'approved')
    and coalesce(ch.total_amount, 0) - coalesce(ev.amount_paid, 0) > 0
  )                                                          as is_payable,
  (bk.starts_at >= now())                                    as is_upcoming
from public.amenity_bookings bk
join public.amenities am                 on am.id = bk.amenity_id
join public.communities c                on c.id = bk.community_id
left join public.community_settings cs   on cs.community_id = bk.community_id
left join lateral (
  select sum(x.amount) as total_amount
    from public.amenity_booking_charges x
   where x.booking_occurrence_id = bk.id
) ch on true
left join lateral (
  select sum(e.amount) as amount_paid
    from public.amenity_financial_events e
    join public.amenity_booking_charges x on x.id = e.booking_charge_id
   where x.booking_occurrence_id = bk.id
     and e.event_type = 'payment'
) ev on true;

comment on view public.resident_booking_overview is
  'A resident''s own amenity bookings with what they owe on each. Balance arithmetic identical to amenity_ledger_overview.';

grant select on public.resident_booking_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 6. settle_amenity_booking_payment
--
-- **This function is what `US-2.12` asks for**, and the story is not about the
-- gateway. The pain point is *"amenity booking payments can fail even after
-- money has been deducted"*, which is not a gateway defect: it is a payment
-- recorded in one transaction and a booking confirmed in another, with a crash
-- in between.
--
-- So: on success, write the payment, append the event, confirm the booking,
-- notify the resident, notify the staff -- one transaction, all of it or none.
-- On failure, write the payment with its reason, append the event, **leave the
-- booking exactly as it was**, and tell the resident. Also one transaction.
--
-- The second half is the one that gets forgotten and the one the story is about.
-- A failed payment must not leave a half-confirmed booking that a resident
-- believes they hold.
--
-- Money moves against a CHARGE, not against a booking -- `0023`'s design, and
-- the reason a refund can say which deposit it refunded. The payment is
-- attributed to the booking's largest charge, which for every booking this
-- endpoint can settle is its only one.
-- ---------------------------------------------------------------------------

-- The booking half of `payment_as_outcome`. A different table, the same five
-- facts, and the same rule: what a client is told about an attempt is read back
-- from the row that recorded it.
create or replace function public.booking_payment_as_outcome(p_event_id uuid)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
           'payment_id',       e.id,
           'status',           case when e.event_type = 'payment'
                                    then 'succeeded' else 'failed' end,
           'failure_code',     case when e.event_type = 'payment'
                                    then null else e.reason end,
           'instrument_label', e.instrument_label,
           'amount',           e.amount
         )
    from public.amenity_financial_events e
   where e.id = p_event_id;
$$;

comment on function public.booking_payment_as_outcome(uuid) is
  'The five facts a client needs about a booking payment attempt, read from the ledger row.';

create or replace function public.find_booking_payment(
  p_booking_id uuid,
  p_key        text
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_key          text := nullif(btrim(coalesce(p_key, '')), '');
  v_id           uuid;
  v_target       uuid;
begin
  if v_key is null then
    return null;
  end if;

  select bk.community_id into v_community_id
    from public.amenity_bookings bk where bk.id = p_booking_id;

  if v_community_id is null or not public.is_own_booking(p_booking_id) then
    return null;
  end if;

  select e.id, x.booking_occurrence_id into v_id, v_target
    from public.amenity_financial_events e
    join public.amenity_booking_charges x on x.id = e.booking_charge_id
   where e.community_id = v_community_id
     and e.payment_reference = v_key
   limit 1;

  if v_id is null then
    return null;
  end if;

  if v_target is distinct from p_booking_id then
    raise exception 'That idempotency key already settled a different booking.'
      using errcode = 'HB409';
  end if;

  return public.booking_payment_as_outcome(v_id);
end;
$$;

comment on function public.find_booking_payment(uuid, text) is
  'Look up a prior booking-payment attempt by idempotency key, before any gateway is called.';

grant execute on function public.find_booking_payment(uuid, text) to authenticated;

drop function if exists public.settle_amenity_booking_payment(uuid, jsonb);
create or replace function public.settle_amenity_booking_payment(
  p_booking_id uuid,
  p_payload    jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_membership   uuid;
  v_status       public.booking_status;
  v_amenity      text;
  v_charge_id    uuid;
  v_key          text := nullif(btrim(coalesce(p_payload ->> 'idempotency_key', '')), '');
  v_outcome      text := lower(coalesce(p_payload ->> 'status', ''));
  v_amount       numeric(12, 2) := (p_payload ->> 'amount')::numeric;
  v_charged      numeric(12, 2);
  v_paid         numeric(12, 2);
  v_outstanding  numeric(12, 2);
  v_id           uuid;
  v_target       uuid;
begin
  select bk.community_id, bk.booked_by_membership_id, bk.status, am.name
    into v_community_id, v_membership, v_status, v_amenity
    from public.amenity_bookings bk
    join public.amenities am on am.id = bk.amenity_id
   where bk.id = p_booking_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  -- Not filtered by `event_type`, unlike `record_amenity_payment`. A key
  -- identifies an attempt, and a replayed attempt that was declined must return
  -- the decline. `0023`'s unique index is on
  -- `(community_id, event_type, payment_reference)`, so falling through would not
  -- even be refused: it would write a `payment` beside the `payment_failed` that
  -- already exists and confirm a booking off the back of a card that declined.
  if v_key is not null then
    select e.id, x.booking_occurrence_id into v_id, v_target
      from public.amenity_financial_events e
      join public.amenity_booking_charges x on x.id = e.booking_charge_id
     where e.community_id = v_community_id
       and e.payment_reference = v_key
     limit 1;

    if v_id is not null then
      if v_target is distinct from p_booking_id then
        raise exception 'That idempotency key already settled a different booking.'
          using errcode = 'HB409';
      end if;
      return public.booking_payment_as_outcome(v_id);
    end if;
  end if;

  if not public.is_own_booking(p_booking_id) then
    raise exception 'You may only pay for your own booking.' using errcode = '42501';
  end if;

  if v_key is null then
    raise exception 'A payment needs an idempotency key.' using errcode = '22004';
  end if;

  if v_outcome not in ('succeeded', 'failed') then
    raise exception 'A settlement must be succeeded or failed.' using errcode = '22P02';
  end if;

  if v_status not in ('requested', 'approved') then
    raise exception 'This booking can no longer be paid for.' using errcode = '23514';
  end if;

  select id, amount into v_charge_id, v_charged
    from public.amenity_booking_charges
   where booking_occurrence_id = p_booking_id
   order by amount desc
   limit 1;

  if v_charge_id is null then
    raise exception 'This booking has nothing to pay.' using errcode = 'HB409';
  end if;

  select coalesce(sum(x.amount), 0), coalesce(sum(e.amount), 0)
    into v_charged, v_paid
    from public.amenity_booking_charges x
    left join public.amenity_financial_events e
           on e.booking_charge_id = x.id and e.event_type = 'payment'
   where x.booking_occurrence_id = p_booking_id;

  v_outstanding := greatest(v_charged - v_paid, 0);

  if v_outstanding <= 0 then
    raise exception 'This booking has already been paid.' using errcode = 'HB409';
  end if;

  if v_amount is null or v_amount <> v_outstanding then
    raise exception 'A payment must settle the full outstanding balance.'
      using errcode = '23514';
  end if;

  insert into public.amenity_financial_events (
    community_id, booking_charge_id, event_type, amount, payment_reference,
    reason, notes, instrument_label, actor_membership_id
  )
  values (
    v_community_id,
    v_charge_id,
    case when v_outcome = 'succeeded' then 'payment' else 'payment_failed' end,
    v_amount,
    v_key,
    case when v_outcome = 'failed'
         then nullif(btrim(coalesce(p_payload ->> 'failure_code', '')), '')
         else null end,
    -- `simulator:` here does the job `provider = 'simulator'` does on `payments`.
    -- The ledger has no provider column, so this prefix is the only thing in an
    -- admin's export that says the money did not move.
    case when v_outcome = 'succeeded'
         then 'simulator: ' || coalesce(p_payload ->> 'instrument_label', 'payment')
         else 'simulator: declined' end,
    nullif(btrim(coalesce(p_payload ->> 'instrument_label', '')), ''),
    v_membership
  )
  returning id into v_id;

  if v_outcome = 'succeeded' then
    -- The half that makes this one transaction rather than two.
    update public.amenity_bookings
       set status            = 'approved',
           approved_at       = coalesce(approved_at, now()),
           aggregate_version = aggregate_version + 1,
           updated_at        = now()
     where id = p_booking_id
       and status = 'requested';
  end if;

  if v_membership is not null then
    perform public.notify_member(
      v_membership,
      case when v_outcome = 'succeeded' then 'payment.succeeded' else 'payment.failed' end,
      jsonb_build_object(
        'title', case when v_outcome = 'succeeded'
                      then 'Booking confirmed' else 'Payment failed' end,
        'body',  case when v_outcome = 'succeeded'
                      then v_amenity || ' is booked and paid for.'
                      else 'Your booking payment did not go through. The booking is unchanged.' end,
        'url',   '/resident/amenities',
        'booking_id', p_booking_id,
        'failure_code', p_payload ->> 'failure_code'
      )
    );
  end if;

  -- **Corrected 2026-08-12.** This was `notify_community_staff`, which is every
  -- admin *and every manager*. A department manager has no role in amenity
  -- bookings at all -- no department owns an amenity -- and the link goes to
  -- `/admin/amenities`, which their portal has no route for, so the click
  -- bounced them silently to their own overview. Admins only.
  if v_outcome = 'succeeded' then
    perform public.notify_community_roles(
      v_community_id,
      array['admin'],
      'amenity.booking_paid',
      jsonb_build_object(
        'title', 'An amenity booking was paid',
        'body',  v_amenity,
        'url',   '/admin/amenities?booking=' || p_booking_id::text,
        'booking_id', p_booking_id
      ),
      v_membership
    );
  end if;

  return public.booking_payment_as_outcome(v_id);
end;
$$;

comment on function public.settle_amenity_booking_payment(uuid, jsonb) is
  'Settle a booking payment and confirm the booking in ONE transaction, or leave both alone. This is the transaction US-2.12 asks for.';

grant execute on function public.settle_amenity_booking_payment(uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- 7. The notice board
--
-- `notices` has had no row security since the baseline, so every authenticated
-- user in the project can currently read every community's notices. This
-- migration is the first resident read of that table, so the policy lands here.
--
-- Members see **published** notices. Staff see everything, because a draft is
-- theirs and the admin dashboard reads this table through the caller's client --
-- a policy that hid drafts from admins would break a screen that works today.
-- ---------------------------------------------------------------------------

drop view if exists public.resident_notice_overview;
create view public.resident_notice_overview
with (security_invoker = true) as
select
  n.id,
  n.community_id,
  n.title,
  n.body,
  n.category,
  initcap(n.urgency)                       as urgency,
  n.urgency                                as stored_urgency,
  coalesce(n.published_at, n.created_at)   as published_at,
  n.created_at,
  pr.full_name                             as author_name
from public.notices n
left join public.community_memberships m on m.id = n.author_membership_id
left join public.profiles pr             on pr.id = m.profile_id
where n.published_at is not null;

comment on view public.resident_notice_overview is
  'Published notices with their category, urgency and author. Drafts are excluded here as well as by policy -- the view is the resident''s, not a filter over theirs.';

grant select on public.resident_notice_overview to authenticated;

alter table public.notices enable row level security;

drop policy if exists notices_read on public.notices;
create policy notices_read on public.notices
  for select to authenticated
  using (
    (public.is_community_member(community_id) and published_at is not null)
    or public.is_community_admin(community_id)
    or exists (
      select 1 from public.community_memberships m
       where m.community_id = notices.community_id
         and m.profile_id = auth.uid()
         and m.role = 'manager'
         and m.status = 'active'
         and m.ended_at is null
    )
  );

drop policy if exists notices_admin_write on public.notices;
create policy notices_admin_write on public.notices
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

-- ---------------------------------------------------------------------------
-- 8. The numbers registered to a flat
--
-- `Profile.jsx` lets a resident add a phone number to their flat without going
-- through an admin, and the prototype implements it by inventing a whole *user*
-- -- name, role, status and all. That cannot be done here and should not be:
-- `profiles.id` references `auth.users`, so a person with no account cannot be a
-- profile, and manufacturing a membership for a phone number would put someone
-- in the community's member count who cannot log in and never agreed to join.
--
-- A flat contact is a different kind of thing from a member, so it gets its own
-- table. It is a phone number the household wants the gate and the office to
-- have -- the spouse who is home in the afternoon, the parent who visits -- and
-- it grants nothing at all.
--
-- Scoped to the unit rather than to the resident who added it, because that is
-- what the screen says: *"Numbers Registered to Flat B-1204"*. When they move
-- out, the number belongs to the flat's history and not to them.
-- ---------------------------------------------------------------------------

create table if not exists public.unit_contacts (
  id                  uuid primary key default gen_random_uuid(),
  community_id        uuid not null references public.communities(id) on delete cascade,
  unit_id             uuid not null references public.units(id) on delete cascade,
  added_by_membership_id uuid references public.community_memberships(id) on delete set null,
  full_name           text not null,
  phone_e164          varchar(20) not null,
  relationship        text,
  is_active           boolean not null default true,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (unit_id, phone_e164)
);

create index if not exists unit_contacts_unit_idx
  on public.unit_contacts (unit_id) where is_active;

comment on table public.unit_contacts is
  'Extra phone numbers a household registers against its flat. Not memberships: they grant nothing and their holder has no account.';

-- The two kinds of person on that screen, in one list, each labelled with what
-- it actually is. `source` is what stops a caller having to guess from a null
-- column, and it is what lets the screen render a real member and a bare phone
-- number without pretending they are the same thing.
drop view if exists public.household_overview;
create view public.household_overview
with (security_invoker = true) as
select
  m.id::text                                       as id,
  'member'                                         as source,
  r.unit_id,
  m.community_id,
  coalesce(pr.full_name, 'Resident')               as full_name,
  pr.phone_e164,
  initcap(r.relationship_type::text)               as relationship,
  r.is_primary_contact,
  case m.status
    when 'active'    then 'Active'
    when 'pending'   then 'Pending'
    when 'suspended' then 'Suspended'
    else 'Ended'
  end                                              as status,
  r.started_at::timestamptz                        as since
from public.unit_residencies r
join public.community_memberships m on m.id = r.membership_id
left join public.profiles pr        on pr.id = m.profile_id
where r.ended_at is null

union all

select
  uc.id::text                                      as id,
  'contact'                                        as source,
  uc.unit_id,
  uc.community_id,
  uc.full_name,
  uc.phone_e164,
  coalesce(nullif(btrim(uc.relationship), ''), 'Contact') as relationship,
  false                                            as is_primary_contact,
  'Contact'                                        as status,
  uc.created_at                                    as since
from public.unit_contacts uc
where uc.is_active;

comment on view public.household_overview is
  'Everyone and everything registered to a flat: residents with accounts, and contact numbers that are not people in the system. `source` says which.';

grant select on public.household_overview to authenticated;

create or replace function public.add_unit_contact(
  p_membership_id uuid,
  p_payload       jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community_id uuid;
  v_unit_id      uuid;
  v_name         text := nullif(btrim(coalesce(p_payload ->> 'full_name', '')), '');
  v_phone        text := nullif(btrim(coalesce(p_payload ->> 'phone_e164', '')), '');
  v_id           uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'A number may only be added to your own flat.'
      using errcode = '42501';
  end if;

  if v_phone is null then
    raise exception 'A contact needs a phone number.' using errcode = '23514';
  end if;

  select m.community_id into v_community_id
    from public.community_memberships m where m.id = p_membership_id;

  -- The flat is resolved from the residency, never from the request. A unit id
  -- in a body is a unit id somebody can change.
  select r.unit_id into v_unit_id
    from public.unit_residencies r
   where r.membership_id = p_membership_id
     and r.ended_at is null
   order by r.is_primary_contact desc, r.started_at desc
   limit 1;

  if v_unit_id is null then
    raise exception 'You are not registered to a flat.' using errcode = 'HB409';
  end if;

  -- The same number added twice is the same number, not an error worth showing
  -- somebody. The name is refreshed, because a correction is the likeliest
  -- reason anyone repeats this.
  insert into public.unit_contacts (
    community_id, unit_id, added_by_membership_id, full_name, phone_e164,
    relationship
  )
  values (
    v_community_id,
    v_unit_id,
    p_membership_id,
    coalesce(v_name, 'Flat contact'),
    v_phone,
    nullif(btrim(coalesce(p_payload ->> 'relationship', '')), '')
  )
  on conflict (unit_id, phone_e164) do update
     set full_name  = excluded.full_name,
         is_active  = true,
         updated_at = now()
  returning id into v_id;

  return v_id;
end;
$$;

comment on function public.add_unit_contact(uuid, jsonb) is
  'Register another phone number against the caller''s own flat. Idempotent on the number; the flat comes from the residency, not the request.';

grant execute on function public.add_unit_contact(uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- 9. The contact directory
--
-- §5.6. `Profile.jsx` renders five hard-coded numbers -- a gate, an office, a
-- plumber, an electrician, a fire room -- which is the stale-by-construction
-- version of exactly what `US-2.9` asks for: a directory somebody can trust.
--
-- Departments already carry a name, a category, contact details and hours, and
-- admins maintain them for reasons of their own. Serving the directory from
-- them means it stays current as a side effect of work that already happens,
-- which is the only kind of freshness that survives contact with a real
-- committee.
--
-- **Two gaps, recorded rather than papered over.**
--
-- `US-2.10` wants a *building* representative, and nothing in this schema ties a
-- department or a person to a building. Out of scope here; §8 of the design
-- document holds it.
--
-- And there is no emergency flag. The prototype's list labels each number --
-- *"Emergency / Gate"*, *"Administrative"*, *"Maintenance Staff"* -- and the
-- nearest thing a department has is `category`, which is free text an admin
-- types. So `category` is what this view returns, and nothing here decides which
-- categories mean *emergency*: inferring that from a text match would be a
-- classification invented in SQL, wrong the first time somebody writes
-- "Emergencies". If the product wants the distinction it is one boolean on
-- `departments`, and that table belongs to the admin workstream.
-- ---------------------------------------------------------------------------

drop view if exists public.management_contact_overview;
create view public.management_contact_overview
with (security_invoker = true) as
select
  d.id,
  d.community_id,
  d.name,
  coalesce(nullif(btrim(d.category), ''), 'Management') as category,
  d.description,
  d.contact_phone_e164                                 as phone_e164,
  d.contact_email::text                                as email,
  d.opens_at,
  d.closes_at,
  d.hours,
  pr.full_name                                         as head_name,
  pr.phone_e164                                        as head_phone_e164
from public.departments d
left join public.community_memberships hm on hm.id = d.manager_membership_id
left join public.profiles pr              on pr.id = hm.profile_id
where d.is_active
  and d.status = 'active';

comment on view public.management_contact_overview is
  'The resident contact directory, served from departments so it stays current as a side effect of admin work rather than as a task nobody owns.';

grant select on public.management_contact_overview to authenticated;

-- ---------------------------------------------------------------------------
-- 10. Row-level security for the two tables that had none
--
-- `unit_residencies` is the worst of the gaps this file closes: it is the table
-- that says who lives in which flat, it is reachable through PostgREST, and it
-- has been readable by every authenticated user in the project since the
-- baseline. A resident may see their own flat's occupants -- which is what the
-- screen shows them -- and an admin may see the community's.
--
-- `departments` is milder but the same shape. It is now read by every member for
-- the directory, so it says so rather than relying on nobody having tried.
-- ---------------------------------------------------------------------------

alter table public.unit_residencies enable row level security;
alter table public.unit_contacts    enable row level security;
alter table public.departments      enable row level security;

drop policy if exists unit_residencies_read on public.unit_residencies;
create policy unit_residencies_read on public.unit_residencies
  for select to authenticated
  using (
    public.is_own_membership(membership_id)
    or exists (
      select 1
        from public.unit_residencies mine
        join public.community_memberships m on m.id = mine.membership_id
       where mine.unit_id = unit_residencies.unit_id
         and mine.ended_at is null
         and m.profile_id = auth.uid()
    )
    or exists (
      select 1 from public.community_memberships m
       where m.id = unit_residencies.membership_id
         and public.is_community_admin(m.community_id)
    )
  );

drop policy if exists unit_contacts_read on public.unit_contacts;
create policy unit_contacts_read on public.unit_contacts
  for select to authenticated
  using (
    public.is_community_admin(community_id)
    or exists (
      select 1
        from public.unit_residencies r
        join public.community_memberships m on m.id = r.membership_id
       where r.unit_id = unit_contacts.unit_id
         and r.ended_at is null
         and m.profile_id = auth.uid()
    )
  );

-- No write policy. `add_unit_contact` is SECURITY DEFINER and resolves the flat
-- itself, which is the only way a resident can add a number to their own flat
-- and to no other.

drop policy if exists departments_read on public.departments;
create policy departments_read on public.departments
  for select to authenticated
  using (public.is_community_member(community_id));

drop policy if exists departments_admin_write on public.departments;
create policy departments_admin_write on public.departments
  for all to authenticated
  using (public.is_community_admin(community_id))
  with check (public.is_community_admin(community_id));

-- ---------------------------------------------------------------------------
-- 11. The module catalogue
--
-- Two of the six rows `0022` set can now be raised, using the codes that
-- actually exist -- see the correction recorded in `0032` §7 and in `0022`
-- itself.
-- ---------------------------------------------------------------------------

update public.feature_catalog set backend_status = 'partial',
  backend_note = 'Residents can list and pay their own invoices through the simulated gateway (0033). Nothing runs a billing cycle.'
 where code = 'maintenance-billing';

update public.feature_catalog set backend_status = 'partial',
  backend_note = 'Residents read published notices (0033). Scheduling a notice for a future date has no backend.'
 where code = 'notice-board';
