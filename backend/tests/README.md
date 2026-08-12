# Core Tests Documentation

> **Note:** This file is generated from test docstrings by running `uv run pytest --collect-only --generate-test-docs` from `backend`.

## `test_access_request_phone.py`
No description provided.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_optional_access_request_phone_is_nullable_and_validated` | No description provided. |
| `test_legacy_access_request_phone_constraint_is_removed` | No description provided. |


## `test_amenity_mapping.py`
Unit tests for the amenity translation layer.

These cover the boundary between what the database stores and what the amenity
subsystem renders. The database side -- the exclusion constraint, the advisory
lock in ``amenity_occurrence_guard``, the derived ``payment_status``, RLS -- cannot
be tested here, because no migration has been applied anywhere. That gap is stated
in DECISIONS_NEEDED E1 rather than papered over: the tests below are about the
half that *can* be checked from Python.

Two of them exist specifically to pin down decisions that differ from the demo,
so that changing either is a test failure rather than a silent behaviour change:
the ledger's ``availableActions`` rules, and the collapse of a multi-day request
into one approval row.

*Total tests in this file: 74*

| Test Function | Description |
|---------------|-------------|
| `test_booking_mode_round_trips[shared-Shared]` | A true round trip, unlike the complaint statuses: three values each way. |
| `test_booking_mode_round_trips[exclusive-Exclusive]` | A true round trip, unlike the complaint statuses: three values each way. |
| `test_booking_mode_round_trips[hybrid-Hybrid]` | A true round trip, unlike the complaint statuses: three values each way. |
| `test_unknown_booking_mode_is_rejected_not_guessed` | None, so the caller can 400 rather than silently making an exclusive hall shared -- which would let two parties be booked into it at once. |
| `test_unknown_stored_booking_mode_reads_shared` | No description provided. |
| `test_amenity_status_reads_inactive_when_unknown` | Defaulting to Active would advertise a facility on the strength of a typo. |
| `test_weekday_round_trips_on_iso_numbering[1-Monday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[2-Tuesday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[3-Wednesday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[4-Thursday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[5-Friday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[6-Saturday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_round_trips_on_iso_numbering[7-Sunday]` | ISO numbering, so `extract(isodow from d)` in SQL means the same thing. |
| `test_weekday_accepts_a_number_as_well_as_a_name` | A client that has already learnt the stored form should not be forced back through the display form to talk to us. |
| `test_weekday_rejects_out_of_range_and_nonsense` | No description provided. |
| `test_weekday_list_is_sorted_and_deduplicated` | No description provided. |
| `test_unrecognised_days_are_dropped_not_stored` | A CHECK constraint rejects the whole array for one bad element, which would turn a typo in one checkbox into a failed save of all thirty settings. |
| `test_weekday_list_survives_a_full_round_trip` | No description provided. |
| `test_twelve_hour_clock[06:00-6:00 AM]` | No description provided. |
| `test_twelve_hour_clock[00:00-12:00 AM]` | No description provided. |
| `test_twelve_hour_clock[12:00-12:00 PM]` | No description provided. |
| `test_twelve_hour_clock[18:30-6:30 PM]` | No description provided. |
| `test_twelve_hour_clock[23:59-11:59 PM]` | No description provided. |
| `test_opening_hours_matches_the_seeded_string` | ``amenitiesManagementMock`` stores '6:00 AM - 10:00 PM' and the card renders it verbatim, so the format is not ours to choose. |
| `test_postgres_time_is_truncated_for_the_time_input` | ``<input type="time">`` shows an empty field for '06:00:00'. |
| `test_amenity_row_reproduces_the_card_shape` | Every field ``AmenityCard`` reads, under the name it reads it by. |
| `test_badges_come_from_the_view_not_from_a_stored_constant` | The mock stores `pendingRequests: 5` for an amenity with one pending request and `outstandingDues: 4800` against 1600 in charges. Both are derived here, so the badge cannot disagree with the tab it links to. |
| `test_outstanding_dues_is_a_json_number_not_a_string` | The catalogue formats it with Intl.NumberFormat; a string would render as a plausible-looking total after concatenation. |
| `test_missing_image_is_an_empty_string_not_null` | The card branches on `amenity.image` and renders a placeholder icon for a falsy value, so '' is a supported value rather than a gap. |
| `test_no_capacity_means_no_limit_not_zero` | The Reading Lounge has no booking limit. Zero would mean an amenity nobody can book, which is what an inactive status is for. |
| `test_detail_carries_both_copies_of_the_duplicated_fields` | ``normalizeAmenityRecord`` writes bookingMode at the top level AND in bookingSettings, and different components read different ones. The database stores each once; the duplication stops at the DTO. |
| `test_detail_renders_weekdays_as_names` | No description provided. |
| `test_booking_row_reproduces_the_seeded_booking_shape` | No description provided. |
| `test_resident_id_is_the_membership_id_the_people_endpoint_returns` | So the dashboard's `users.find(u => u.id === booking.residentId)` resolves. Same rule the money endpoints follow. |
| `test_series_id_is_emitted_as_the_booking_group_too` | The frontend groups multi-day requests by `bookingGroupId`. Our series id IS that group, so it goes out under both names -- one for the code that exists, one that reads correctly. |
| `test_a_block_is_blocked_on_the_timeline_and_a_booking_is_not` | The timeline colours from `state`, which has four values, while the lifecycle has seven. |
| `test_completed_is_carried_from_the_view_not_recomputed` | The view derives it from the clock; recomputing here would give two answers that disagree for a booking finishing during the request. |
| `test_a_block_has_no_resident_rather_than_a_placeholder` | No description provided. |
| `test_day_count_travels_with_every_day_of_a_request` | The approvals table needs it to say '3 days' -- one click now decides the whole request. |
| `test_guests_are_attached_by_series_not_by_day` | A guest list belongs to the request; a three-day booking does not have three copies of the same guests. |
| `test_charge_override_distinguishes_free_from_default` | None means 'use the configured fee'; 0 means 'free'. Collapsing them would make a waived fee indistinguishable from no decision. |
| `test_ledger_row_reproduces_the_transaction_shape` | No description provided. |
| `test_every_ledger_figure_is_a_number_not_a_string` | The ledger summary reduces over these in the browser. |
| `test_ledger_figures_come_from_the_view_not_from_python` | Reproduces the seeded txn-gym-1001: 1000 + 100 charged, 1100 paid. |
| `test_refund_and_damage_histories_split_the_event_stream` | No description provided. |
| `test_audit_trail_is_ordered_and_includes_the_lifecycle` | Assembled from the booking's own timestamps and its financial events, not from a second audit table that would have to agree with them. |
| `test_cancelled_booking_puts_a_cancellation_in_the_trail` | No description provided. |
| `test_a_completed_booking_with_a_deposit_can_be_refunded_or_charged` | No description provided. |
| `test_a_fully_refunded_booking_offers_neither` | `refunded` is financially closed: there is nothing left to return. |
| `test_a_pending_booking_offers_no_refund` | Nothing has been held yet, and the booking has not happened. |
| `test_a_future_confirmed_booking_can_be_force_cancelled` | No description provided. |
| `test_a_past_booking_cannot_be_force_cancelled` | There is nothing left to prevent. |
| `test_an_already_force_cancelled_booking_cannot_be_again` | No description provided. |
| `test_settings_omitted_entirely_is_not_the_same_as_settings_empty` | None means 'do not touch the settings row'; {} means 'a save with no changed fields'. The RPC branches on the difference. |
| `test_only_the_fields_the_caller_sent_are_translated` | A field left out is left alone. `exclude_unset`, not `exclude_none`. |
| `test_a_null_booking_limit_is_sent_rather_than_dropped` | Null means 'no limit', which is a value. Dropping it would make clearing the limit impossible. |
| `test_settings_translate_to_the_column_names_the_migration_uses` | No description provided. |
| `test_a_maximum_shorter_than_the_minimum_is_refused` | No description provided. |
| `test_closing_before_opening_is_refused` | Otherwise the amenity has no bookable minute and every booking fails with a confusing message instead of this one. |
| `test_an_unknown_maintenance_interval_is_refused` | No description provided. |
| `test_a_resident_request_needs_at_least_one_date` | No description provided. |
| `test_a_resident_request_carries_no_flat` | The flat is read from the caller's own residency, so a resident cannot book against somebody else's unit by editing the request. |
| `test_an_admin_booking_names_the_resident_but_not_the_flat` | The flat is resolved from their residency, so the ledger charges a unit that exists. |
| `test_a_payment_must_be_above_zero` | No description provided. |
| `test_a_damage_deduction_needs_a_reason` | No description provided. |
| `test_a_rejection_needs_a_reason_code` | No description provided. |
| `test_a_refund_request_cannot_name_its_own_amount` | A refund whose amount is a request parameter is a refund somebody can ask to be larger. It is computed from the deposit in Postgres. |
| `test_an_added_charge_must_be_positive` | No description provided. |
| `test_amount_parses_numeric_from_either_shape[None-0.0]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |
| `test_amount_parses_numeric_from_either_shape[0-0.0]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |
| `test_amount_parses_numeric_from_either_shape[1600.00-1600.0]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |
| `test_amount_parses_numeric_from_either_shape[1600.0-1600.0]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |
| `test_amount_parses_numeric_from_either_shape[0.50-0.5]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |
| `test_amount_parses_numeric_from_either_shape[1234.567-1234.57]` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. |


## `test_auth_verification.py`
Email-confirmation behavior at the password-session boundary.

Production defaults to confirmation-required. Local/test bypass is explicit and
the backend still enforces the setting when GoTrue returns a session.

Google identities are deliberately untouched here -- the provider has already
verified the address, and an OAuth JWT is not required to carry the claim at all
(``docs/BACKEND_CHANGES.md``).

*Total tests in this file: 12*

| Test Function | Description |
|---------------|-------------|
| `test_an_unconfirmed_address_cannot_sign_in_by_default` | No description provided. |
| `test_refusing_an_unconfirmed_address_revokes_the_minted_session` | No description provided. |
| `test_explicit_local_override_allows_an_unconfirmed_test_account` | No description provided. |
| `test_a_provider_that_refuses_the_grant_reports_the_same_reason` | With **Confirm email** on, GoTrue refuses first -- one code either way, so the caller's experience does not depend on a dashboard toggle. |
| `test_a_confirmed_address_still_signs_in` | No description provided. |
| `test_a_wrong_password_is_not_reported_as_an_unconfirmed_address` | Only GoTrue's own ``email_not_confirmed`` earns the specific message; everything else stays the generic answer that reveals nothing. |
| `test_a_session_without_a_user_record_fails_closed` | No description provided. |
| `test_resending_asks_for_a_signup_link_pointing_at_the_confirmation_page` | The link has to land on the page that spends the token hash; anywhere else and the user meets a confirm button with nothing to confirm. |
| `test_the_service_intent_is_appended_as_a_query_parameter_not_concatenated` | ``?a=b?intent=…`` is one parameter, not two.  The confirmation page parses ``token_hash`` out of this query string. A second ``?`` makes ``URLSearchParams`` swallow everything after it into one value, so the link arrives with nothing to confirm -- a base URL that already carries a query has to extend it with ``&``. |
| `test_no_intent_leaves_the_confirmation_url_exactly_as_it_was` | Every non-professional signup keeps the URL the setup document names. |
| `test_resending_stays_silent_when_the_provider_fails` | A resend that raised on unknown addresses would enumerate accounts. |
| `test_email_confirmation_is_read_from_where_supabase_actually_puts_it` | Supabase nests the flag in ``user_metadata``. Reading only the top level left the field false for every real caller -- inert while nothing consults it, and a total lockout for whoever first writes ``if not email_verified``. |


## `test_department_mapping.py`
The department wire/storage seams.

Three of them, and each one is a place where a silent mistranslation would be
invisible until a user noticed the wrong thing on screen:

* ``Active``/``Inactive`` vs the stored ``active``/``archived`` (A6),
* Postgres ``time`` vs the ``HH:MM`` an ``<input type="time">`` accepts,
* the jsonb patch the RPC reads, where a *missing* key and a ``null`` value mean
  opposite things.

*Total tests in this file: 22*

| Test Function | Description |
|---------------|-------------|
| `test_department_status_to_wire[active-Active]` | No description provided. |
| `test_department_status_to_wire[archived-Inactive]` | No description provided. |
| `test_department_status_to_storage[Active-active]` | No description provided. |
| `test_department_status_to_storage[Inactive-archived]` | No description provided. |
| `test_department_status_to_storage[  inactive -archived]` | No description provided. |
| `test_department_status_to_storage[archived-archived]` | No description provided. |
| `test_unknown_department_status_is_rejected_not_guessed` | No description provided. |
| `test_department_status_round_trips_both_ways` | Unlike the complaint statuses, this mapping is a true bijection. |
| `test_clock_time[08:00:00-08:00]` | No description provided. |
| `test_clock_time[23:59:00-23:59]` | No description provided. |
| `test_clock_time[00:00:00-00:00]` | No description provided. |
| `test_clock_time[07:30:00.000000-07:30]` | No description provided. |
| `test_clock_time[9:05:00-09:05]` | No description provided. |
| `test_clock_time[None-None]` | No description provided. |
| `test_clock_time[-None]` | No description provided. |
| `test_clock_time[garbage-None]` | No description provided. |
| `test_staff_payload_omits_untouched_fields` | A key the caller never sent must not appear in the patch.  The RPC treats key presence as "change this", so including ``phone: null`` for a member whose phone was never mentioned would erase a stored number. |
| `test_staff_payload_keeps_an_explicit_null` | An explicit null is a request to clear, and must survive. |
| `test_staff_payload_carries_the_id_that_makes_it_an_update` | No description provided. |
| `test_blank_staff_id_is_not_an_id` | The create form seeds ``id: ''``; sending it would look like an update. |
| `test_update_request_distinguishes_omitted_from_null` | The whole partial-update contract rests on this. |
| `test_operating_hours_rejects_a_non_clock_string` | A bad time must fail at the edge, not become a null column silently. |


## `test_dispatcher.py`
The job dispatcher.

What is covered, stated plainly because it is easy to overclaim: **this
exercises the loop, not the engine.** Every decision the dispatcher causes --
who is free, who gets the offer, what the resident is told -- happens inside
``0037``, which this suite has no database to run, so none of it can run here.
What is tested is the part written in Python:
claiming, per-task isolation, the failure path, and the lifecycle.

The rule these tests exist to protect is the inverse of the push sender's, and
the inversion is the reason the file is worth reading:

    The sender may not duplicate. The dispatcher may not drop.

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_the_dispatcher_starts_unconditionally` | No configuration gate, unlike `PushSender`.  An environment with no VAPID keypair is one where push is legitimately off. There is no equivalent for dispatch: a process that silently did not dispatch would be indistinguishable from a department where nobody was free, which is the failure with no alarm attached. |
| `test_stopping_is_clean_and_repeatable` | Cancellation is not an error, and stopping twice is not either.  The lifespan calls `stop` on the way out of a process that may already be tearing down; a second call raising would turn an orderly shutdown into a traceback in the logs. |
| `test_every_claimed_task_is_fired` | No description provided. |
| `test_a_row_without_a_task_id_is_skipped_rather_than_fired` | Defensive, and cheap. A malformed row reaching `fire` would send a null task id to Postgres, which answers `missing` -- correct, but a round trip to learn something the row already said. |
| `test_the_batch_size_reaches_the_claim` | No description provided. |
| `test_a_failing_task_is_recorded_and_its_lease_released` | The lease is the whole reason this branch exists.  A task that raised and was left claimed is five minutes of nothing happening to a job somebody is waiting on -- `fail_dispatch_task` clears `claimed_at` so the next tick can pick it up. |
| `test_one_failing_task_does_not_abandon_the_rest_of_the_batch` | No description provided. |
| `test_a_failure_to_record_the_failure_is_swallowed` | Both calls fail and the batch survives anyway.  The database being unreachable is exactly when `fire` raises *and* `fail` cannot be written. Letting the second exception out would take down the loop for the whole process at the moment it is least able to recover. |
| `test_the_loop_survives_a_failing_claim` | A transient database failure must not silently stop every dispatch in the process. The loop logs and comes back on the next tick. |
| `test_the_dispatcher_knows_nothing_about_task_kinds` | The kinds appear in `0037`, not here.  `fire_dispatch_task` maps a kind to an action beside the actions it dispatches to, so adding a fifth kind is a migration and nothing else. If this assertion ever fails, a branch on `kind` has appeared in Python and the engine has started living in two places. |


## `test_domain_contract.py`
Regression checks for the membership-centred database contract.

They complement, rather than replace, applying the migrations to Supabase.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_baseline_contains_core_tenant_tables` | No description provided. |
| `test_baseline_preserves_key_invariants` | No description provided. |
| `test_baseline_uses_membership_scoped_workflows` | No description provided. |
| `test_registration_baseline_has_search_and_atomic_request_workflows` | No description provided. |


## `test_formatting.py`
Server-side display formatting.

These strings are rendered verbatim by a frontend we cannot change, so the exact
output is a contract, not an implementation detail. The expected values are taken
from frontend/src/data/complaints.js and notices.js.

*Total tests in this file: 14*

| Test Function | Description |
|---------------|-------------|
| `test_time_ago_matches_the_frontend_vocabulary[delta0-Just now]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta1-Just now]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta2-5m ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta3-2h ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta4-4h ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta5-1d ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta6-2d ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta7-1w ago]` | No description provided. |
| `test_time_ago_matches_the_frontend_vocabulary[delta8-2mo ago]` | No description provided. |
| `test_time_ago_never_renders_a_negative` | Clock skew must not produce '-3h ago' in front of a resident. |
| `test_long_date_matches_the_notices_format` | No description provided. |
| `test_long_date_has_no_zero_padded_day` | 'July 8, 2026', never 'July 08, 2026' -- %-d is unavailable on Windows. |
| `test_parse_instant_accepts_both_postgrest_shapes` | No description provided. |
| `test_naive_datetimes_are_treated_as_utc` | No description provided. |


## `test_invitation_logic.py`
Unit tests for the pure invite-redemption decision and token hashing.

*Total tests in this file: 8*

| Test Function | Description |
|---------------|-------------|
| `test_valid_invite_returns_none` | No description provided. |
| `test_missing_invite_is_invalid` | No description provided. |
| `test_redeemed_invite_is_used` | No description provided. |
| `test_expired_invite_is_expired` | No description provided. |
| `test_naive_expiry_is_treated_as_utc` | No description provided. |
| `test_hash_is_stable_and_matches` | No description provided. |
| `test_code_normalization_round_trip` | No description provided. |
| `test_generated_code_uses_unambiguous_alphabet` | No description provided. |


## `test_logging.py`
No description provided.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_transport_loggers_do_not_emit_request_headers` | No description provided. |


## `test_membership_set.py`
The tenancy seam, after it learned about more than one community.

`app/api/deps.py` used to resolve exactly one membership -- `order by
is_default_community desc limit 1` -- and every handler in the product was
written against that. A service person breaks the assumption: they belong to as
many communities as have hired them, and their calendar is the union of all of
them.

The change was made additively, and **additive is a claim these tests exist to
check.** Three properties, in order of how expensive they would be to discover
in production:

1. `get_active_membership` still returns what it returned before, still takes a
   `Principal`, and can still be called directly rather than through FastAPI.
   The last of those is not decoration -- `tests/api/test_session_flow.py` calls
   it positionally to prove the role comes from `community_memberships` and not
   from a token claim, and an earlier draft of this change broke that by
   declaring `Depends(get_membership_set)` in its signature. To FastAPI the two
   read identically; to a caller they do not.
2. Ordering is preserved: default first, then oldest.
3. `require_community_role` refuses a community the caller is not in, which is
   what stops a resource id in a URL from being an authorization decision.

`app/api/deps.py` belongs to the parallel auth workstream. These tests are the
evidence offered with that review request.

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_a_single_membership_caller_gets_exactly_what_they_got_before` | The overwhelmingly common case, and the one every existing handler is written against. |
| `test_get_active_membership_is_still_callable_with_a_principal` | The regression that a draft of this change actually introduced.  Declaring `Depends(get_membership_set)` on this function reads identically to FastAPI and breaks every direct call, including the session-flow test that proves the role is not read from the token. |
| `test_the_default_membership_is_the_first_row` | `is_default_community desc, created_at` is applied by Postgres, so the resolver must not re-sort -- it must trust position. |
| `test_every_active_membership_is_returned_not_just_the_first` | The whole reason the seam changed: a service person hired by three societies has three memberships and one calendar. |
| `test_the_resolver_reads_community_memberships_once` | Dropping `limit 1` must not have cost a second round trip. Membership is resolved on every single request; a duplicated read here is a duplicated read everywhere. |
| `test_a_caller_with_no_active_membership_is_still_refused` | Unchanged behaviour, and worth pinning: this 403 is what stands between a signed-in stranger and every membership-guarded route in the product. |
| `test_for_community_returns_none_rather_than_guessing` | `MembershipSet` deliberately carries no raising method -- the 403 lives in `deps.py`, so `app/domain` never has to import `app/core`. |
| `test_require_community_role_refuses_a_community_the_caller_is_not_in` | The point of the helper. A community id arriving on a resource -- a job, an application, a department -- must never be an authorization decision by itself. |
| `test_require_community_role_refuses_the_right_community_with_the_wrong_role` | Being in the community is not being entitled in it. |
| `test_require_community_role_allows_any_role_when_none_is_named` | "Are you in this community at all" is a real question, asked by every read a member of it may make. |


## `test_money_mapping.py`
Unit tests for the money translation layer.

These cover the boundary between what the database stores and what the
dashboard renders. The database side (RLS, the RPCs, the double-billing index)
cannot be tested here -- no migration has been applied anywhere -- so every test
below is about the half that *can* be checked, and the untested half is stated
plainly in DECISIONS_NEEDED E1 rather than implied to be covered.

*Total tests in this file: 40*

| Test Function | Description |
|---------------|-------------|
| `test_invoice_status_to_wire[draft-Unpaid]` | No description provided. |
| `test_invoice_status_to_wire[issued-Unpaid]` | No description provided. |
| `test_invoice_status_to_wire[partially_paid-Unpaid]` | No description provided. |
| `test_invoice_status_to_wire[paid-Paid]` | No description provided. |
| `test_invoice_status_to_wire[void-Void]` | No description provided. |
| `test_unknown_invoice_status_reads_unpaid` | An unrecognised status must not read as Paid.  Defaulting the other way would show a bill as settled on the strength of a typo in a status column. |
| `test_payment_method_round_trips[upi]` | No description provided. |
| `test_payment_method_round_trips[card]` | No description provided. |
| `test_payment_method_round_trips[netbanking]` | No description provided. |
| `test_payment_method_round_trips[cash]` | No description provided. |
| `test_payment_method_round_trips[cheque]` | No description provided. |
| `test_payment_method_round_trips[bank_transfer]` | No description provided. |
| `test_payment_method_accepts_frontend_spellings[UPI-upi]` | No description provided. |
| `test_payment_method_accepts_frontend_spellings[upi-upi]` | No description provided. |
| `test_payment_method_accepts_frontend_spellings[Net Banking-netbanking]` | No description provided. |
| `test_payment_method_accepts_frontend_spellings[Credit Card-card]` | No description provided. |
| `test_payment_method_accepts_frontend_spellings[  cash  -cash]` | No description provided. |
| `test_unknown_payment_method_is_none_not_a_guess` | No description provided. |
| `test_unknown_stored_method_passes_through` | A method added by a later migration renders as itself rather than disappearing from the payment history. |
| `test_bill_period_matches_the_seeded_string` | No description provided. |
| `test_bill_period_with_no_dates_is_a_one_time_charge` | The clubhouse charge in data/payments.js carries exactly this string. |
| `test_bill_period_with_one_date_shows_that_date` | No description provided. |
| `test_bill_period_accepts_real_dates_and_single_days` | No description provided. |
| `test_amount_parses_numeric_from_either_shape[None-0.0]` | PostgREST has sent `numeric` as both a JSON number and a string across SDK versions, and a string reaching the frontend's reduce() concatenates. |
| `test_amount_parses_numeric_from_either_shape[4250.00-4250.0]` | PostgREST has sent `numeric` as both a JSON number and a string across SDK versions, and a string reaching the frontend's reduce() concatenates. |
| `test_amount_parses_numeric_from_either_shape[4250-4250.0]` | PostgREST has sent `numeric` as both a JSON number and a string across SDK versions, and a string reaching the frontend's reduce() concatenates. |
| `test_amount_parses_numeric_from_either_shape[0.005-0.01]` | PostgREST has sent `numeric` as both a JSON number and a string across SDK versions, and a string reaching the frontend's reduce() concatenates. |
| `test_invoice_row_reproduces_the_frontend_payment_shape` | Every key `Maintenance.jsx` and the resident Payments page read must be present and hold the value they expect. |
| `test_amount_is_a_json_number_not_a_string` | `payments.reduce((a, c) => a + c.amount, 0)` concatenates strings, and the resulting "42504250" renders as a plausible rupee total. |
| `test_partially_paid_invoice_still_reads_unpaid_and_keeps_its_full_amount` | `amount` is what the flat was billed -- the column is headed "Amount". The balance travels separately, which is why the totals tile is a server aggregate rather than a sum of this field. |
| `test_paid_invoice_carries_the_settling_payment` | No description provided. |
| `test_vacant_flat_has_no_resident_rather_than_a_placeholder` | The dashboard already renders `user ? user.name : 'Resident'`, so null is a shape it handles -- and the debt belongs to the flat regardless. |
| `test_overdue_is_carried_from_the_view_not_recomputed` | No description provided. |
| `test_an_invoice_needs_at_least_one_line` | No description provided. |
| `test_a_line_amount_must_be_positive` | No description provided. |
| `test_blank_flat_is_treated_as_absent` | The create form seeds text inputs with '', and '' is not a flat. |
| `test_a_payment_must_be_above_zero` | No description provided. |
| `test_billing_settings_distinguish_omitted_from_null` | Clearing the maintenance rate stops billing runs; leaving it alone must not. Only key presence tells the two apart. |
| `test_due_day_cannot_land_outside_february` | No description provided. |
| `test_invoice_prefix_rejects_characters_that_would_break_a_number` | No description provided. |


## `test_notification_links.py`
Every notification `url` a migration emits must be a route the app has.

`SECURITY_PORTAL_DESIGN.md` states the contract and, until this file, the
consequence too: *"a notification whose `url` 404s is a defect that no test
catches."* It does not 404, which is what makes it expensive --
`NotificationBell.jsx:72` calls `navigate(item.url)` with whatever the row says,
and `App.jsx`'s catch-all sends anything unmatched to `/`. The user taps a real
notification, arrives at the marketing page, and there is no error anywhere: not
in the browser console, not in the API log, not in a test run.

Four of them were wrong when this file was written, in three different ways --
a route that was deleted, a route that never existed, and a route belonging to a
portal other than the recipient's. All three are the same mistake: the URL was
written from memory of the navigation rather than from the navigation.

**How the route table is derived.** From `App.jsx` itself, by walking the nested
`<Route>` elements and joining each one to its parents, with `AUTH_ROUTES`
resolved out of `routes/authRoutes.js`. Keeping a copy of the table here would
reproduce the original defect one layer down: a second list of routes that is
right on the day it is written.

**What a match means.** That the path resolves to a mounted route. Query
parameters are dropped before matching, deliberately, because an ignored
parameter is a missing feature and an unroutable path is a broken link -- two
different defects that deserve two different answers.

The second one is answered further down, by `test_the_ignored_query_parameters_
are_the_ones_on_record`. Ten notification links carry a parameter; some of the
screens they land on do not read it, which lands the user on the right page
looking at the wrong row. That set is written down rather than asserted empty:
several of those screens belong to other workstreams and are already filed under
`docs/potential issues/`. Recording it keeps the list from growing quietly, and
makes a screen that starts honouring its parameter a test change rather than a
silent improvement nobody notices.

*Total tests in this file: 11*

| Test Function | Description |
|---------------|-------------|
| `test_the_route_table_is_actually_parsed` | If the walker silently produced nothing, everything below would pass. |
| `test_the_matcher_rejects_the_four_urls_this_file_was_written_for[/security/visitors?pass={param}]` | Proof the check has teeth.  A link checker that cannot fail is worth nothing, and this one is only ever exercised by a passing suite. These are the four values that were in the migrations on 2026-08-11; each must still be judged unroutable. |
| `test_the_matcher_rejects_the_four_urls_this_file_was_written_for[/worker/jobs/{param}]` | Proof the check has teeth.  A link checker that cannot fail is worth nothing, and this one is only ever exercised by a passing suite. These are the four values that were in the migrations on 2026-08-11; each must still be judged unroutable. |
| `test_the_matcher_rejects_the_four_urls_this_file_was_written_for[/worker/jobs?job={param}]` | Proof the check has teeth.  A link checker that cannot fail is worth nothing, and this one is only ever exercised by a passing suite. These are the four values that were in the migrations on 2026-08-11; each must still be judged unroutable. |
| `test_the_matcher_rejects_the_four_urls_this_file_was_written_for[/security-manager/shifts?shift={param}]` | Proof the check has teeth.  A link checker that cannot fail is worth nothing, and this one is only ever exercised by a passing suite. These are the four values that were in the migrations on 2026-08-11; each must still be judged unroutable. |
| `test_the_component_behind_every_linked_route_can_be_read` | The parameter check below is only worth as much as this resolution.  If a path stopped resolving to a file -- renamed folder, re-exported component, a route whose element is an inline expression -- the checks that follow would quietly pass by having nothing to look at. |
| `test_the_ignored_query_parameters_are_the_ones_on_record` | A link that lands on the right screen and shows the wrong row.  `/security/shifts?shift=` was the case that prompted this: the path was corrected on 2026-08-11 and the guard still arrived at a fortnight of rows with nothing marking the one they had been told about. Fixing that without checking the others would have left five more of the same, each invisible for the same reason -- the link works, so nothing reports it.  Equality, not a subset. A screen that starts honouring its parameter must leave this set, so the record cannot drift into an allow-list nobody prunes. |
| `test_every_notification_url_resolves_to_a_mounted_route` | No description provided. |
| `test_the_python_mirror_matches_the_javascript_rule_table` | A second implementation is only safe while it is checked against the first. The four rules are read out of `portalUrl.js` by name rather than by behaviour -- enough to fail loudly if somebody adds a fifth here and not there, or renames one.  **The sub-screen list is compared by content**, not by name. Naming was enough while the list was three entries nobody touched; `work-orders` joined it on 2026-08-12 for the work-order notification repoint, and a name check would have passed just as happily with the JavaScript half of that change reverted -- leaving every one of the seven links bouncing a department manager home while this file asserted they were fine. |
| `test_a_managers_notification_lands_somewhere_they_may_go[manager]` | No description provided. |
| `test_a_managers_notification_lands_somewhere_they_may_go[security-manager]` | No description provided. |


## `test_openapi_spec.py`
Guards on the API surface itself.

``docs/openapi.yaml`` is generated from the code, which makes it trustworthy
right up until someone changes a route and forgets to regenerate. This module is
what stops that: a stale spec fails the build rather than quietly shipping a lie
to whoever generates a client from it.

The other two tests catch failure modes that have no other alarm -- a router
written but never mounted (nothing errors; the endpoints simply do not exist),
and an endpoint that forgets its auth dependency (it works perfectly, for
everyone).

*Total tests in this file: 30*

| Test Function | Description |
|---------------|-------------|
| `test_checked_in_spec_matches_the_code` | docs/openapi.yaml must be what `scripts/export_openapi.py` produces now. |
| `test_every_router_is_mounted[/api/v1/admins]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/notices]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/complaints/{complaint_id}]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/departments]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/invoices]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/billing-settings]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/amenity-reports]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/settings]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/service-providers/me]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/worker/communities]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/worker/snapshot]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/worker/calendar]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/departments/{department_id}/candidates]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/conversations]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/work-orders/{work_order_id}]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/complaints/{complaint_id}/schedule-request]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/security/posts]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/dashboard/snapshot]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/auth/session]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/admin/access-requests]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/communities/search]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_every_router_is_mounted[/api/v1/onboarding/community]` | One representative path per router.  A router that is written but never added to ``api_router`` raises nothing at all -- its endpoints just silently do not exist, and the first person to notice is whoever calls them. |
| `test_retired_endpoints_stay_retired[/api/v1/dashboard/admin]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_retired_endpoints_stay_retired[/api/v1/residents]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_retired_endpoints_stay_retired[/api/v1/registrations]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_retired_endpoints_stay_retired[/api/v1/payments]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_retired_endpoints_stay_retired[/api/v1/amenities]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_retired_endpoints_stay_retired[/api/v1/settings/modules]` | Paths deliberately removed by the frontend wiring audit.  Each was either duplicating an endpoint the frontend already calls or serving a read the shared dashboard snapshot serves. Re-adding one is a decision, not an accident, so it should have to delete a line here first. See ``docs/FRONTEND_WIRING_AUDIT.md``. |
| `test_no_protected_endpoint_is_missing_its_auth_dependency` | An endpoint that forgets `Depends(get_current_user)` still works -- for everyone. Nothing else in the stack notices. |


## `test_payment_simulator.py`
The simulated gateway — the outcomes, and the things it must never keep.

Two groups matter more than the rest.

**The failure paths.** They are the reason the simulator exists rather than a
stub that always succeeds: with a real provider in test mode, a decline is a card
you have to go and find, and here it is one expiry date. A demonstration that
cannot be run in front of somebody is not a demonstration.

**The absence of the card.** `SimulatedOutcome` has three fields and none of them
may carry a number, a CVV or an expiry. That is a property no assertion about a
return value catches by accident, so it is asserted directly.

*Total tests in this file: 24*

| Test Function | Description |
|---------------|-------------|
| `test_the_published_test_card_succeeds` | No description provided. |
| `test_the_same_card_with_a_past_expiry_fails` | `PO`'s worked example, and the whole point of a simulator that can be made to fail on demand rather than by accident. |
| `test_a_card_is_good_through_the_last_day_of_its_expiry_month` | The off-by-one that would decline a valid card for up to a month. |
| `test_each_test_card_declines_with_its_own_reason[4000000000000002-card_declined]` | Distinct codes, because "declined" and "no money" are different things to tell somebody, and the client is the one phrasing it. |
| `test_each_test_card_declines_with_its_own_reason[4000000000009995-insufficient_funds]` | Distinct codes, because "declined" and "no money" are different things to tell somebody, and the client is the one phrasing it. |
| `test_each_test_card_declines_with_its_own_reason[4000000000000069-card_expired]` | Distinct codes, because "declined" and "no money" are different things to tell somebody, and the client is the one phrasing it. |
| `test_the_expiry_rule_wins_over_a_cards_own_verdict` | So the demonstration works on whichever card is to hand, rather than only on the one with no other opinion. |
| `test_a_number_that_is_not_a_test_card_is_refused_before_anything_else` | §11.3, and the argument is not convenience. A simulator that accepted any Luhn-valid number is one that will eventually be handed a real card by somebody being helpful, and at that moment this is an application holding a live PAN with none of the obligations that implies. |
| `test_a_refused_number_is_not_echoed_back_even_masked` | Four digits of a number we have just declined to accept is still four digits of a number we declined to accept. |
| `test_a_malformed_cvv_is_card_invalid[12]` | No description provided. |
| `test_a_malformed_cvv_is_card_invalid[12345]` | No description provided. |
| `test_a_malformed_cvv_is_card_invalid[abc]` | No description provided. |
| `test_a_malformed_cvv_is_card_invalid[]` | No description provided. |
| `test_a_month_that_is_not_a_month_is_card_invalid` | No description provided. |
| `test_a_well_formed_vpa_succeeds` | No description provided. |
| `test_the_failure_handles_decline[failure@okaxis]` | The UPI half of the expiry demonstration. `Payments.jsx` enables UPI and disables cards, so without this the failure path is unreachable from the only payment screen that exists. |
| `test_the_failure_handles_decline[fail@upi]` | The UPI half of the expiry demonstration. `Payments.jsx` enables UPI and disables cards, so without this the failure path is unreachable from the only payment screen that exists. |
| `test_the_failure_handles_decline[FAILURE@okaxis]` | The UPI half of the expiry demonstration. `Payments.jsx` enables UPI and disables cards, so without this the failure path is unreachable from the only payment screen that exists. |
| `test_no_vpa_at_all_succeeds_because_the_screen_collects_none` | The shipped modal renders UPI as the single enabled option and its Confirm button sends no instrument. Refusing that would mean the endpoint could not be called from the screen it was built for. |
| `test_a_malformed_vpa_is_refused` | No description provided. |
| `test_an_unknown_method_fails_rather_than_passing_by_default` | *Passes by default* is about instruments, not about methods nobody built. |
| `test_no_field_of_the_outcome_carries_the_card` | §11.3. The card is read by this function and discarded inside it; what leaves is a receipt line. |
| `test_the_label_is_the_last_four_and_nothing_more` | No description provided. |
| `test_the_same_input_always_gives_the_same_answer` | No randomness anywhere. A demo that fails one time in ten is a demo nobody can run twice, and a failure you cannot reproduce is one you cannot show. |


## `test_pg_errors.py`
Mapping of Postgres/PostgREST SQLSTATEs to our error hierarchy.

These matter because the RPCs in migration 0012 signal authorization and state
failures through SQLSTATEs rather than message text -- if this mapping is wrong,
a 403 silently becomes a 500.

*Total tests in this file: 17*

| Test Function | Description |
|---------------|-------------|
| `test_known_sqlstates_map_to_typed_errors[HB403-AuthorizationError-forbidden]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[HB404-NotFoundError-not_found]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[HB409-ConflictError-conflict]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[HBSEP-ConflictError-professional_account_separate]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[23505-ConflictError-unique_violation]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[23503-ValidationError-foreign_key_violation]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[23514-ValidationError-check_violation]` | No description provided. |
| `test_known_sqlstates_map_to_typed_errors[42501-AuthorizationError-insufficient_privilege]` | No description provided. |
| `test_custom_codes_forward_their_message` | Our own RPCs write messages meant for the caller. |
| `test_builtin_codes_do_not_leak_postgres_text` | A constraint message can quote a row value, so it must not be forwarded. |
| `test_unknown_code_falls_back_without_leaking` | No description provided. |
| `test_error_without_a_code_is_handled` | Not every exception from the SDK is an APIError. |
| `test_custom_error_returns_our_own_refusals` | No description provided. |
| `test_custom_error_declines_everything_that_is_not_ours[exc0]` | A standard SQLSTATE's message is Postgres' words, not ours to forward. |
| `test_custom_error_declines_everything_that_is_not_ours[exc1]` | A standard SQLSTATE's message is Postgres' words, not ours to forward. |
| `test_custom_error_declines_everything_that_is_not_ours[exc2]` | A standard SQLSTATE's message is Postgres' words, not ours to forward. |
| `test_custom_error_declines_one_of_ours_that_arrived_empty` | The caller must always be able to fall back to its own wording. |


## `test_professional_membership_symmetry.py`
The separate-account rule, enforced in both directions.

`20260812113000_professional_membership_symmetry.sql` is the product owner's
2026-08-12 ruling on `docs/potential issues/16`: a registered service
professional is assumed not to live in any association, so the rule is identity
separation and the direction nobody was watching -- register as a professional
first, join as a resident second -- has to be refused too.

These are static checks, like `test_service_professional_migrations.py`. They
cannot show that Postgres refuses the insert; the CI job that resets a local
Supabase and applies every migration could, and does not cover this yet. What
they can show is that the statement the database will run says what the ruling
says, and that the refusal it raises is one the API knows how to shape -- which
is the half that would otherwise be found by an administrator staring at a 500.

*Total tests in this file: 11*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_the_last_unapplied_migration` | Forward-only: filename order is apply order, and `090300` is the floor.  Not "is the last file in the directory". That was the original assertion and it was wrong within the day: `20260812120000` was written after this one, and a later migration arriving is the system working, not a regression here. What has to hold is that this file lands after everything it depends on -- `20260811162409`, whose trigger body it extends, and the four `20260812090…` files that were the unapplied frontier when it was written. |
| `test_a_professional_is_refused_a_resident_manager_or_admin_membership` | No description provided. |
| `test_the_worker_security_refusal_it_was_extracted_from_survives` | The body is a copy of an applied one; the copy must not lose anything. |
| `test_the_new_predicate_is_marked_as_the_difference` | House discipline: a copied body marks every departure `-- CHANGED`. |
| `test_the_definer_function_keeps_its_execute_revocation` | No description provided. |
| `test_existing_violations_are_reported_and_never_repaired` | Which identity to keep is the account holder's decision, not a DDL file's.  Ending the membership evicts a household from its portal; deleting the provider row destroys hiring history. A migration that picked one would be making that call for every affected account at once, in the dark. |
| `test_no_applied_migration_was_edited_to_make_room_for_this` | The refusal is added forward; `…162409` still reads as it was applied. |
| `test_the_stale_search_comment_is_reissued_against_the_installed_body` | `0034:531` still promises behaviour `…162409` replaced.  The comment says a community with no coordinates "sorts last rather than being hidden". The body installed today filters on `c.location is not null` and orders by a distance with no `nulls last`, so such a community is hidden. A `comment on` is what `\df+` shows a reader inside the database, where there is no migration file beside it to correct the record. |
| `test_claiming_an_invite_on_a_professional_account_is_a_conflict` | No description provided. |
| `test_an_unrecognised_claim_failure_does_not_leak_postgres_text` | No description provided. |


## `test_push_sender.py`
The Web Push sender.

What is covered, stated plainly because it is easy to overclaim: **this exercises
our half.** The HTTP call to Google, Mozilla or Apple is replaced, and no browser
is involved -- there is no service worker in the frontend yet (§10.6), so push
ships backend-complete and unverifiable end to end until one exists. What is
tested is claiming, payload construction, per-subscription isolation, and the
failure rules -- which is where the decisions are.

The rule these tests exist to protect is the one the SSE hub does not have:

    The hub may drop. The sender may not duplicate.

*Total tests in this file: 21*

| Test Function | Description |
|---------------|-------------|
| `test_the_sender_does_not_start_without_a_keypair` | Not an error. An environment with no VAPID keys is one where push is off, not one that is broken -- the same shape as `0024` no-opping without `pg_cron`. |
| `test_the_sender_starts_when_configured` | No description provided. |
| `test_malformed_configuration_is_treated_as_no_configuration[problem0]` | Checked at startup so the answer is known before a resident subscribes, rather than discovered on the first send -- a browser allowed to subscribe against a key we cannot sign with silently never receives anything. |
| `test_malformed_configuration_is_treated_as_no_configuration[problem1]` | Checked at startup so the answer is known before a resident subscribes, rather than discovered on the first send -- a browser allowed to subscribe against a key we cannot sign with silently never receives anything. |
| `test_malformed_configuration_is_treated_as_no_configuration[problem2]` | Checked at startup so the answer is known before a resident subscribes, rather than discovered on the first send -- a browser allowed to subscribe against a key we cannot sign with silently never receives anything. |
| `test_the_configuration_problem_never_echoes_key_material` | It is written to a log line. Half a private key in a log file is a leaked private key. |
| `test_the_push_is_rendered_from_the_stored_notification` | One source, so the feed row and the lock-screen line can never tell different stories about the same event (§10.8). |
| `test_the_push_carries_the_detail_rather_than_open_the_app` | `US-2.1`'s pain point is a notification that makes a sound and shows nothing. A generic push would be a milder version of the exact failure the story exists to fix, and a resident being asked to approve someone needs the name to decide. |
| `test_a_push_never_carries_a_field_it_was_not_asked_for` | The one thing that may never appear in a push body is the visitor security code (§5.4, §10.8). Enforced by construction: the renderer reads three keys and copies nothing else. |
| `test_the_tag_defaults_to_the_notification_id` | Unique, so it never coalesces. Wrongly merging two complaints into one line loses a notification; wrongly showing two lines costs a scroll. |
| `test_a_writer_opts_into_coalescing_with_a_tag` | Three gate attempts for one visitor should collapse into one notification, not stack into three. |
| `test_a_delivered_push_clears_the_failure_streak` | No description provided. |
| `test_a_gone_subscription_is_deleted_not_retried[404]` | Retrying a dead endpoint forever is how you get rate-limited by a push service, and no amount of retrying revives it. |
| `test_a_gone_subscription_is_deleted_not_retried[410]` | Retrying a dead endpoint forever is how you get rate-limited by a push service, and no amount of retrying revives it. |
| `test_a_transient_failure_is_counted_not_deleted[429]` | The subscription is dropped after five of these, in SQL. Nothing here retries the send: the next notification is the retry, because retrying one against a struggling service is how a backlog becomes a herd. |
| `test_a_transient_failure_is_counted_not_deleted[500]` | The subscription is dropped after five of these, in SQL. Nothing here retries the send: the next notification is the retry, because retrying one against a struggling service is how a backlog becomes a herd. |
| `test_a_transient_failure_is_counted_not_deleted[503]` | The subscription is dropped after five of these, in SQL. Nothing here retries the send: the next notification is the retry, because retrying one against a struggling service is how a backlog becomes a herd. |
| `test_every_registered_device_is_sent_to` | A resident with a phone and a laptop has two subscriptions and both should buzz. |
| `test_one_dead_device_does_not_stop_the_others` | Each subscription is dispatched with its exception captured, so a subscription that raises cannot stall a batch. |
| `test_a_recipient_with_no_devices_is_not_an_error` | The ordinary case for a resident who never granted permission. The notification is in the feed; there is simply no phone to reach. |
| `test_a_claimed_row_without_a_recipient_is_skipped` | No description provided. |


## `test_realtime.py`
The dashboard live-update path: frame format, fan-out, and tenant isolation.

Nothing here touches Supabase. The hub's only contact with the database is two
repository functions, so the tests substitute those and drive the rest for real
-- including the asyncio queues, so the concurrency being asserted is the
concurrency that ships.

*Total tests in this file: 32*

| Test Function | Description |
|---------------|-------------|
| `test_frame_data_is_json_not_a_python_repr` | The regression that made every payload unparseable in the browser.  The previous implementation interpolated the dict directly, emitting `{'table': 'complaints'}` -- single-quoted, so `JSON.parse` threw on it. |
| `test_frame_carries_id_and_topic_for_reconnect_and_dispatch` | No description provided. |
| `test_a_payload_containing_a_newline_cannot_split_the_frame` | A raw newline in the data field would end the event early and desynchronise everything after it. json.dumps escapes it. |
| `test_non_serialisable_payload_values_do_not_raise` | `default=str` keeps a stray datetime from killing the whole stream. |
| `test_dispatch_routes_each_row_to_its_own_community_only` | No description provided. |
| `test_every_subscriber_in_a_community_gets_the_same_event` | Two admins on one community must cost one query, not two -- which only works if a single fetched row fans out to both. |
| `test_events_for_an_unwatched_community_are_discarded_not_buffered` | No description provided. |
| `test_cursor_advances_to_the_highest_id_seen` | No description provided. |
| `test_a_full_queue_degrades_instead_of_blocking_the_poller` | One stalled browser must not stop delivery for everyone else. |
| `test_a_lagging_admin_is_told_to_resync_on_the_topic_already_wired` | Dropped events are unrecoverable, so the client is sent the topic its existing listener already reacts to by re-fetching the snapshot. |
| `test_a_lagging_resident_is_not_told_to_refresh_the_admin_dashboard` | `dashboard.refresh` means 're-read the admin snapshot', which a resident would be refused. It is also a topic `0028` restricts to {admin,manager}, so sending it to a resident here would contradict the migration. |
| `test_subscribe_yields_live_events_and_unregisters_on_exit` | No description provided. |
| `test_reconnecting_with_a_last_event_id_replays_the_gap` | A browser that drops its connection mid-stream must not lose the join requests that arrived while it was away. |
| `test_a_failing_poll_does_not_kill_the_loop` | A transient Supabase error must not silently freeze every dashboard in the process -- the loop has to survive and try again. |
| `test_the_poller_does_not_query_when_nobody_is_listening` | Idle cost must be zero, not one query per tick forever. |
| `test_a_resident_does_not_receive_a_neighbours_join_request` | The disclosure this migration exists to close. |
| `test_an_admin_still_receives_join_requests` | No description provided. |
| `test_every_role_in_the_list_matches_not_just_the_first` | No description provided. |
| `test_a_role_audience_excludes_every_role_not_listed` | An allowlist, not a denylist on 'resident' -- so a role added to the enum later is excluded by default rather than included by default. |
| `test_a_member_audience_reaches_exactly_one_membership` | No description provided. |
| `test_a_community_audience_reaches_everyone_in_the_community` | No description provided. |
| `test_a_row_written_before_the_migration_reads_as_community_wide` | `audience` is `not null default 'community'`, but a `select` against an older projection can still hand us a row without the key. |
| `test_an_unclassifiable_row_is_delivered_to_nobody` | `sse_events_audience_shape_check` makes these unwritable. If one arrives anyway the reader must fail closed -- guessing 'community' is a leak. |
| `test_dispatch_applies_the_filter_per_subscriber_not_per_community` | Two people on one community, one row, two different outcomes -- from a single fetch. The filter has to sit inside the fan-out loop, not around it. |
| `test_the_cursor_advances_past_rows_nobody_in_the_audience_is_watching` | Filtering must not make the poller re-read the same row forever. |
| `test_the_backfill_uses_the_same_filter_as_live_dispatch` | A reconnect must not be the way round the audience. The query narrows and `accepts` decides, so a row the query lets through is still dropped. |
| `test_a_failing_backfill_yields_no_frames_not_an_exception` | No description provided. |
| `test_the_backfill_narrowing_clause_never_widens_past_the_caller` | The PostgREST `or=` is hand-written, so what it asks for is worth asserting: the caller's own membership and role, and nothing else. |
| `test_a_filter_value_that_is_not_a_role_or_a_uuid_is_dropped_not_escaped` | These come from a membership row, so this should be unreachable. If it ever is reachable, the clause must degrade to something harmless rather than carry an operator into the query string -- and `accepts` still gates. |
| `test_an_admin_receives_the_pending_join_requests` | The field the sidebar badge counts. Absent from the payload until now, which is why the badge could never render. |
| `test_a_resident_never_receives_other_residents_join_requests` | These rows carry a third party's name, email and phone. Role is the only thing standing between a resident and that list. |
| `test_a_security_guard_does_not_receive_them_either` | The gate is an allowlist on 'admin', not a denylist on 'resident' -- so every other role is excluded too. |


## `test_registration_contracts.py`
No description provided.

*Total tests in this file: 23*

| Test Function | Description |
|---------------|-------------|
| `test_google_and_email_password_are_supported_configured_methods` | No description provided. |
| `test_establishing_a_session_clears_the_preauth_csrf_cookie[establish_session]` | No description provided. |
| `test_establishing_a_session_clears_the_preauth_csrf_cookie[establish_recovery_session]` | No description provided. |
| `test_unsupported_auth_method_fails_closed` | No description provided. |
| `test_auth_methods_can_swap_primary_without_changing_enabled_order` | No description provided. |
| `test_production_refuses_disabled_email_confirmation` | No description provided. |
| `test_password_signup_requires_a_long_password` | No description provided. |
| `test_community_search_reports_an_unapplied_blacklist_schema_migration` | A rollout mismatch must be a safe 503, never a blacklist-bypassing fallback. |
| `test_service_provider_registration_reports_an_unapplied_schema_migration` | Never fall back to separate profile and skill writes during rollout. |
| `test_google_authorize_url_leaves_provider_state_to_supabase` | No description provided. |
| `test_access_request_rejects_client_owned_identity_fields` | No description provided. |
| `test_founder_contract_rejects_inline_profile_image` | No description provided. |
| `test_legacy_bridge_installs_founder_rpc_only_when_missing` | No description provided. |
| `test_founder_rpc_compatibility_migration_replaces_stale_legacy_functions` | No description provided. |
| `test_community_status_compatibility_migration_normalizes_legacy_values` | No description provided. |
| `test_join_and_invitation_flows_do_not_require_an_email_confirmation_claim` | No description provided. |
| `test_access_request_identity_compatibility_migration_preserves_legacy_rows` | No description provided. |
| `test_resident_access_request_decision_rpcs_are_available_for_legacy_projects` | No description provided. |
| `test_resident_approval_handles_both_legacy_and_baseline_unique_indexes` | No description provided. |
| `test_dashboard_realtime_bridge_is_tenant_scoped` | No description provided. |
| `test_auth_method_and_registration_routes_are_mounted` | No description provided. |
| `test_stalled_refresh_does_not_block_public_auth_methods` | Provider I/O must not freeze the login screen's public configuration. |
| `test_dashboard_snapshot_does_not_block_the_api_event_loop` | A slow tenant projection must leave public auth routes schedulable. |


## `test_service_professional_migrations.py`
Executable contracts for the two forward-only professional-flow migrations.

These checks complement the local-Supabase CI job; they do not pretend a SQL
parser is a running Postgres database.

*Total tests in this file: 5*

| Test Function | Description |
|---------------|-------------|
| `test_new_migrations_parse_as_postgresql` | No description provided. |
| `test_proximity_is_radius_bounded_stable_and_capped` | No description provided. |
| `test_registration_and_hiring_remain_database_atomic` | No description provided. |
| `test_definer_functions_have_explicit_execution_grants` | No description provided. |
| `test_funnel_table_is_narrow_allowlisted_and_retained_for_30_days` | No description provided. |


## `test_service_professional_supabase.py`
Real local-Supabase service-professional flow using authenticated user JWTs.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_service_professional_flow_with_real_user_jwts` | No description provided. |
| `test_radius_boundary_stable_top_twenty_and_name_filter` | No description provided. |
| `test_concurrent_registration_creates_one_complete_provider` | No description provided. |
| `test_funnel_retention_removes_only_expired_events` | No description provided. |


## `test_session_portal.py`
Which portal a membership lands in.

`portal` is the single value the frontend routes on -- `PORTAL_ROUTES` in
`frontend/src/routes/authRoutes.js` maps it to a landing route and
`applicationUser()` turns `security-manager` into the one role label four
screens and a route guard branch on. So a wrong answer here does not produce an
error anywhere; it produces a person who quietly never sees their own portal.

That is exactly what happened. `security-manager` was derived from a `manager`
membership naming a security department, and **nothing in the system writes a
`manager` membership** -- `hire_service_applicant` (`0035:918`) mints `security`
or `worker` and no other code path mints one at all. The portal was satisfiable
by no user the product can create, which is a defect no test could see because
no test asked. These are those questions.

The seam under test is `_portal_for`, called with a membership row exactly as
`get_session_context` reads it. `get_service_client` is monkeypatched, so the
last assertion in each case -- *which tables were read* -- is available, and it
is worth having: the roster read must not fire for a resident.

*Total tests in this file: 7*

| Test Function | Description |
|---------------|-------------|
| `test_resident_admin_and_worker_are_their_own_portal` | No description provided. |
| `test_plain_guard_stays_at_the_gate` | No description provided. |
| `test_security_rank_seniority_opens_the_manager_portal[manager]` | The spelling real people have.  `gate_admin_community_for` (`0040:589`) admits a `security` membership whose active roster row ranks manager or supervisor, and `supervisor` is in that list deliberately -- a supervisor holds the manager's writes, so the guard portal would leave them permissions with no screen. |
| `test_security_rank_seniority_opens_the_manager_portal[supervisor]` | The spelling real people have.  `gate_admin_community_for` (`0040:589`) admits a `security` membership whose active roster row ranks manager or supervisor, and `supervisor` is in that list deliberately -- a supervisor holds the manager's writes, so the guard portal would leave them permissions with no screen. |
| `test_manager_of_a_security_department_still_resolves` | Unreachable today, and kept: `manager` is a real `membership_role`. |
| `test_manager_of_a_service_department_is_not_a_gate_manager` | The `departments.kind` question is the reason that branch exists. |
| `test_manager_without_a_department_reads_nothing` | No description provided. |


## `test_settings_mapping.py`
Unit tests for the settings and feature-module translation layer.

The database half -- the timezone lookup against ``pg_timezone_names``, the two
cross-field CHECKs behind the billing toggles, the RLS on ``community_settings``,
the catalogue-driven join -- cannot be tested here, because no migration has been
applied anywhere. DECISIONS_NEEDED E1 says so; these tests cover the half Python
owns.

Three of them pin decisions rather than mechanics, so that changing any of them
is a test failure and not a quiet behaviour change:

* ``unitLabelSingular`` is derived from the community type, and Python's fallback
  must produce the same word as the SQL one in ``community_settings_overview``.
  Two implementations of one rule is the reason to test it.
* ``lateFeeAmount`` keeps null as null instead of collapsing to ``0.0``. A fine
  of zero is one somebody configured; a fine of null is one nobody has.
* A module the catalogue lists but the community has no row for reads as its
  default rather than vanishing -- the property that makes an eleventh module
  toggleable the day it is added.

*Total tests in this file: 31*

| Test Function | Description |
|---------------|-------------|
| `test_community_type_label_matches_the_onboarding_select[apartment-Apartment]` | `communityTypeOptions` renders 'layout_villa' with spaces and a slash.  No rule derives that from the stored value, which is why there is a table. |
| `test_community_type_label_matches_the_onboarding_select[layout_villa-Layout / Villa]` | `communityTypeOptions` renders 'layout_villa' with spaces and a slash.  No rule derives that from the stored value, which is why there is a table. |
| `test_community_type_label_matches_the_onboarding_select[APARTMENT-Apartment]` | `communityTypeOptions` renders 'layout_villa' with spaces and a slash.  No rule derives that from the stored value, which is why there is a table. |
| `test_community_type_label_falls_back_rather_than_raising` | An unknown type is a data problem, not a reason to 500 a settings screen. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[Weekly-weekly]` | No description provided. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[weekly-weekly]` | No description provided. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[Monthly-monthly]` | No description provided. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[One-time-once]` | No description provided. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[one time-once]` | No description provided. |
| `test_late_fee_period_accepts_the_label_and_the_stored_value[once-once]` | No description provided. |
| `test_unrecognised_late_fee_period_is_none_not_a_guess` | The service turns None into a 422 naming the three options.  Defaulting to 'weekly' would mean a typo silently choosing how often a resident is fined. |
| `test_late_fee_period_round_trips_through_its_label` | No description provided. |
| `test_backend_status_labels[implemented-Implemented]` | No description provided. |
| `test_backend_status_labels[partial-Partial]` | No description provided. |
| `test_backend_status_labels[none-Not implemented]` | No description provided. |
| `test_unknown_backend_status_reads_as_not_implemented` | The safe direction: claiming less than exists, never more. |
| `test_profile_carries_both_the_machine_value_and_the_label` | No description provided. |
| `test_preferences_report_whether_the_unit_label_was_chosen` | A screen that cannot tell a default from a choice shows an admin a value they never picked as though they had. |
| `test_sms_broadcast_defaults_to_off` | The one toggle that spends money every time it fires. A missing value must not read as enabled. |
| `test_late_fee_amount_keeps_null_distinct_from_zero` | `_amount` in the money service collapses null to 0.0, which would be wrong here: the CHECK behind `lateFeeEnabled` treats null as 'not configured' and zero as 'configured as nothing'. |
| `test_billing_toggles_carry_the_period_label_alongside_the_value` | No description provided. |
| `test_auto_billing_day_defaults_to_the_first` | Matching the frontend's copy: invoices "on the 1st of every month". |
| `test_a_module_with_no_community_row_reads_as_its_default` | `community_module_overview` is driven by the catalogue, not by `community_modules`. This is the property that makes an eleventh module toggleable on the day it is added rather than invisible until somebody backfills a row for every community. |
| `test_collection_counts_enabled_modules_that_nothing_implements` | The number worth putting on the screen. Six of the ten modules have no backend, so an admin can otherwise switch three of them on and get no hint. |
| `test_collection_counts_agree_with_the_views_own_aggregates` | `community_settings_overview` reports the same two numbers in SQL. If the Python count and the SQL count disagree, one screen shows two truths. |
| `test_an_empty_module_list_is_zeros_not_an_error` | No description provided. |
| `test_a_timezone_with_whitespace_is_rejected_before_the_database_sees_it` | An IANA name never contains whitespace, and a 422 naming the field is a better error than the 409 the RPC would raise. |
| `test_a_timezone_is_trimmed_but_not_otherwise_touched` | Case is left alone: the RPC looks the name up case-insensitively and stores the catalogue's own spelling, so normalising here would be a second opinion. |
| `test_omitting_a_field_is_distinct_from_sending_null` | The whole basis of the patch: null clears the unit-label override and returns to deriving it; an absent key leaves it as it was. |
| `test_an_invite_ttl_beyond_thirty_days_is_rejected` | An invite that outlives a month is not a second factor, it is a credential sitting in an inbox. The database CHECK agrees; this is the earlier of the two. |
| `test_visitor_code_ttl_bounds` | No description provided. |


## `test_unit_residencies_rls_migration.py`
No description provided.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_unit_residencies_policy_does_not_query_itself` | No description provided. |


## `test_units.py`
Flat-code normalisation.

The cases that matter are the ones that come from the frontend's two
incompatible representations of a flat -- see app/domain/units.py.

*Total tests in this file: 13*

| Test Function | Description |
|---------------|-------------|
| `test_normalize_unit_code[C-505-C-505]` | No description provided. |
| `test_normalize_unit_code[A-102-A-102]` | No description provided. |
| `test_normalize_unit_code[B-1204-B-1204]` | No description provided. |
| `test_normalize_unit_code[C-C-505-C-505]` | No description provided. |
| `test_normalize_unit_code[a-A-102-A-102]` | No description provided. |
| `test_normalize_unit_code[B-Admin Office-Admin Office]` | No description provided. |
| `test_normalize_unit_code[B-C-505-C-505]` | No description provided. |
| `test_normalize_unit_code[None-A-102-A-102]` | No description provided. |
| `test_normalize_unit_code[-A-102-A-102]` | No description provided. |
| `test_normalize_unit_code[C--None]` | No description provided. |
| `test_normalize_unit_code[C-None-None]` | No description provided. |
| `test_normalize_unit_code[D-12B-D-12B]` | No description provided. |
| `test_normalisation_is_idempotent` | Applying it twice must not double the prefix -- the bug's exact shape. |


## `test_vocabularies.py`
Status vocabulary mapping.

The frontend puts these exact strings in a `<select>`, so a wrong mapping is a
silently broken dropdown rather than an error.

The stored side has a harder constraint: it must be a member of the baseline's
`public.complaint_status` enum. A value outside that set is a `22P02` from
Postgres, not a bad row -- so `test_every_stored_status_is_a_baseline_enum_member`
is the test that actually protects `PATCH /complaints/{id}`.

*Total tests in this file: 29*

| Test Function | Description |
|---------------|-------------|
| `test_status_to_storage[Pending-open]` | No description provided. |
| `test_status_to_storage[In Progress-in_progress]` | No description provided. |
| `test_status_to_storage[in progress-in_progress]` | No description provided. |
| `test_status_to_storage[RESOLVED-resolved]` | No description provided. |
| `test_status_to_storage[  Pending  -open]` | No description provided. |
| `test_status_to_storage[Cancelled-cancelled]` | No description provided. |
| `test_status_to_storage[Reopened-open]` | No description provided. |
| `test_every_stored_status_is_a_baseline_enum_member[Pending]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_every_stored_status_is_a_baseline_enum_member[In Progress]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_every_stored_status_is_a_baseline_enum_member[Resolved]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_every_stored_status_is_a_baseline_enum_member[Closed]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_every_stored_status_is_a_baseline_enum_member[Reopened]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_every_stored_status_is_a_baseline_enum_member[Cancelled]` | Guards the bug this mapping used to have.  It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which is in the enum, so every such write would have failed against a real database. |
| `test_unknown_status_is_rejected_not_guessed` | An unknown status must surface as an error, not become 'open'. |
| `test_a_filter_matches_every_status_that_renders_as_the_word_asked_for[Pending-expected0]` | No description provided. |
| `test_a_filter_matches_every_status_that_renders_as_the_word_asked_for[In Progress-expected1]` | No description provided. |
| `test_a_filter_matches_every_status_that_renders_as_the_word_asked_for[Resolved-expected2]` | No description provided. |
| `test_a_filter_matches_every_status_that_renders_as_the_word_asked_for[Cancelled-expected3]` | No description provided. |
| `test_an_unrenderable_word_is_rejected_rather_than_matching_nothing` | `Closed` is a stored value, not something this surface ever shows -- so a caller asking for it is a caller guessing. An empty match list would look like "you have none of those". |
| `test_every_word_this_surface_renders_can_be_filtered_by` | The two directions are derived from one map, so this cannot drift -- which is the point of asserting it rather than trusting it. |
| `test_comment_visibility_to_storage[resident-public]` | No description provided. |
| `test_comment_visibility_to_storage[internal-internal]` | No description provided. |
| `test_comment_visibility_to_storage[public-public]` | No description provided. |
| `test_comment_visibility_to_storage[  Resident  -public]` | No description provided. |
| `test_comment_visibility_to_storage[INTERNAL-internal]` | No description provided. |
| `test_every_stored_visibility_satisfies_the_check_constraint[resident]` | The test that actually protects `POST /complaints/{id}/comments`.  Its sibling above would still pass if the map returned `resident` for `resident`, which is exactly the bug that shipped. |
| `test_every_stored_visibility_satisfies_the_check_constraint[public]` | The test that actually protects `POST /complaints/{id}/comments`.  Its sibling above would still pass if the map returned `resident` for `resident`, which is exactly the bug that shipped. |
| `test_every_stored_visibility_satisfies_the_check_constraint[internal]` | The test that actually protects `POST /complaints/{id}/comments`.  Its sibling above would still pass if the map returned `resident` for `resident`, which is exactly the bug that shipped. |
| `test_an_unknown_visibility_is_rejected_rather_than_defaulted` | Not symmetrical with the other unknowns in this module, and deliberately so: guessing `public` here would publish to the resident a comment somebody may have meant to keep internal. |


## `test_work_order_notification_urls.py`
Seven work-order notifications, repointed at the screen that now exists.

`20260812120000_work_order_notification_urls.sql` moves every supervisor-facing
work-order notification in `0037` and `0039` off `/admin/departments?job=<id>`
-- the department *list*, which reads no `job` parameter -- and onto
`departments/{id}/work-orders?job=<id>`, the triage screen. `docs/potential
issues/12` item 4 deferred this until such a screen existed; it does.

These are static checks. Whether Postgres installs these bodies is the local
Supabase CI job's question, and whether the link lands is
`test_notification_links.py`'s -- which reads the same files and checks every
surviving url against `App.jsx`'s route tree, including the per-portal rewrite.
What is left for this file is the part neither can see: that the seven bodies
are the applied text with seven url lines changed and nothing else.

*Total tests in this file: 18*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_migration_it_supersedes` | Filename order is apply order: last declaration of a name wins.  Being the last file in the directory was only ever a proxy for the property that matters (`20260812160000` broke the proxy without touching the property): the repoint must sort after both files it supersedes, and no migration sorting after it may re-declare any of the six functions -- otherwise that later file's body, not this one's, is what runs. |
| `test_every_emission_of_the_dead_url_is_accounted_for` | Seven, counted from the applied files rather than from memory.  The count is the point of this test: a repoint that reaches six of seven leaves one notification pointing at a department list, and it would be the one nobody clicks in testing. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[accept_work_order_offer]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[complete_work_order]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[dispatch_auto_assign]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[dispatch_failed_visit_escalation]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[dispatch_ping_candidates]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_body_is_the_applied_text_with_only_the_url_changed[report_work_order_failure]` | Whole-body extraction, checked line by line against its source.  The copy is mandatory -- both source files are applied and immutable -- and a copy that quietly drops a status check while it is repointing a link is the failure mode the discipline exists to prevent. Every line of the applied body must appear in the new one unless it is a url line. |
| `test_each_changed_line_is_marked_and_is_the_only_change[accept_work_order_offer]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_each_changed_line_is_marked_and_is_the_only_change[complete_work_order]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_each_changed_line_is_marked_and_is_the_only_change[dispatch_auto_assign]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_each_changed_line_is_marked_and_is_the_only_change[dispatch_failed_visit_escalation]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_each_changed_line_is_marked_and_is_the_only_change[dispatch_ping_candidates]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_each_changed_line_is_marked_and_is_the_only_change[report_work_order_failure]` | House discipline: an extracted body marks every departure `-- CHANGED`. |
| `test_the_url_carries_the_department_the_screen_is_scoped_to` | `:departmentId` is in the path under all three portal bases.  A url that named only the job would resolve to no route at all -- there is no `/admin/work-orders` -- so the department is not decoration. |
| `test_no_acl_or_comment_is_restated_from_memory` | `create or replace` keeps the oid, so both survive on their own.  Restating them would mean writing out two opposite postures by hand: `0037`'s three are service_role only and `0039`'s three are granted to `authenticated`. A copy that gets one backwards is a privilege change wearing the clothes of a link fix. |
| `test_the_worker_and_resident_links_in_these_bodies_are_untouched` | Only the supervisor's link moves. The worker's and the resident's do not.  Both were corrected once already (`0036`'s header records `/worker/jobs…` twice), and a body-wide search-and-replace on `?job=` is exactly how they would be broken a third time. |


