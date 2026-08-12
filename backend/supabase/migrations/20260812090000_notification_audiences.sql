-- ---------------------------------------------------------------------------
-- Two notification audiences that were wrong, corrected forward
--
-- Both of these were written as `notify_community_staff`, which is **every
-- admin and every manager in the community**. That was the widest audience
-- available and it was chosen because nothing narrower existed -- not because
-- either event is everybody's business.
--
-- The symptom in both cases was a dead link. A department manager was told an
-- amenity booking had been paid and sent to `/admin/amenities`; a plumbing
-- manager was told about a gate incident and sent to `/admin/security/incidents`.
-- Neither route exists under `/manager`, so `ProtectedRoute` does not show a 403
-- -- it redirects them to their own overview. A click that appears to do nothing.
--
-- Both are audience mistakes rather than routing mistakes, and neither is fixed
-- by adding a rewrite rule. Recorded in `docs/potential issues/14`.
--
-- ## Why this file copies two whole function bodies
--
-- `0033` and `0040` are applied. `backend/supabase/migrations/README.md` used
-- to allow correcting an unapplied file in place precisely so that a one-line
-- change to a string inside a function body would not have to re-declare the
-- entire function -- because the copy is then free to drift from the original.
--
-- That allowance is gone: the linked hosted project was verified on 2026-08-11
-- with everything through `0047` applied. So the copy is now mandatory, and the
-- drift risk it was avoiding is real and unavoidable. What is done about it:
-- the bodies below were extracted mechanically from the applied files, so the
-- starting point is provably the applied text, and every difference from it is
-- marked `-- CHANGED` in place.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 1. settle_amenity_booking_payment -- admins only
--
-- No department owns an amenity. There is no `departments` row a booking
-- points at, no manager whose department it is, and nothing for a manager to
-- do about a payment that succeeded. The product owner confirmed it on
-- 2026-08-12: *"amenity booking is only for the admin. no other department
-- owns it for now."*
-- ---------------------------------------------------------------------------

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

  if v_outcome = 'succeeded' then
    -- CHANGED: was `notify_community_staff(v_community_id, …)`.
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
-- 2. record_security_incident -- admins and *security-department* managers
--
-- The audience below is the same predicate `_portal_for` uses to decide who
-- gets `/security-manager` at all (`auth_service.py`: the membership's own
-- `department_id`, resolved to `departments.kind`). Deliberately mirrored rather
-- than approximated -- if the two ever disagree, somebody is notified about a
-- screen they cannot open, which is exactly the defect being fixed.
--
-- A manager whose membership carries no `department_id` is therefore excluded,
-- even though `can_manage_department` would let them manage the security
-- department. That manager routes to `/manager`, which has no incidents screen,
-- so notifying them would recreate the defect. No path mints such a row --
-- `staff_invitations.department_id` and `hire_service_applicant` both require a
-- department -- so this excludes a row nothing creates.
-- ---------------------------------------------------------------------------

create or replace function public.record_security_incident(
  p_membership_id    uuid,
  p_summary          text,
  p_category         text default 'other',
  p_severity         text default 'medium',
  p_details          text default null,
  p_location_text    text default null,
  p_post_id          uuid default null,
  p_occurred_at      timestamptz default null,
  p_source_client_id text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_summary   text := nullif(btrim(coalesce(p_summary, '')), '');
  v_severity  text := lower(btrim(coalesce(p_severity, 'medium')));
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_id        uuid;
  v_payload   jsonb;   -- CHANGED: both new, for the split audience below.
  v_manager   record;
begin
  if v_summary is null then
    raise exception 'Say what happened.' using errcode = '22004';
  end if;

  if v_client is not null then
    select id into v_id
      from public.security_incidents
     where community_id = v_community and source_client_id = v_client;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.security_incidents
    (community_id, category, severity, summary, details, location_text,
     post_id, occurred_at, reported_by_membership_id, source_client_id)
  values (
    v_community, coalesce(nullif(btrim(lower(coalesce(p_category, ''))), ''), 'other'),
    v_severity, v_summary, nullif(btrim(coalesce(p_details, '')), ''),
    nullif(btrim(coalesce(p_location_text, '')), ''), p_post_id,
    coalesce(p_occurred_at, now()), p_membership_id, v_client)
  returning id into v_id;

  -- The one register write that notifies. A tanker arriving is a record;
  -- something going wrong at the gate at 2am is a message, and `high` or
  -- `critical` is the line between the two.
  if v_severity in ('high', 'critical') then
    -- CHANGED: was one `notify_community_roles(…, array['admin', 'manager'], …)`.
    v_payload := jsonb_build_object(
      'title', 'Security incident reported',
      'body',  v_summary,
      'url',   '/admin/security/incidents'
    );

    perform public.notify_community_roles(
      v_community, array['admin'], 'security.incident', v_payload
    );

    for v_manager in
      select m.id
        from public.community_memberships m
        join public.departments d on d.id = m.department_id
       where m.community_id = v_community
         and m.role::text   = 'manager'
         and m.status       = 'active'
         and m.ended_at is null
         and d.kind         = 'security'
    loop
      perform public.notify_member(v_manager.id, 'security.incident', v_payload);
    end loop;
  end if;

  return v_id;
end;
$$;

comment on function public.record_security_incident(uuid, text, text, text, text, text, uuid, timestamptz, text) is
  'File an incident. High and critical ones notify the community''s admins and its security-department managers; the rest are a record.';

