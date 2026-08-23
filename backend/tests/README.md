# Core Tests Documentation

> **Note:** This file is generated from test docstrings by running `uv run pytest --collect-only --generate-test-docs` from `backend`.

## `test_access_request_phone.py`
No description provided.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_optional_access_request_phone_is_nullable_and_validated` | No description provided. |
| `test_legacy_access_request_phone_constraint_is_removed` | No description provided. |


## `test_admin_raised_complaints_migration.py`
`20260820150000_admin_raised_complaints.sql` -- what a hand-applied file
cannot be allowed to get wrong.

This migration is pasted into the Supabase SQL editor by a person, once, against
a live database. There is no local Supabase in this repository's CI, so nothing
runs it before it runs for real. That raises the value of the checks a static
reader *can* make and narrows them to three questions:

**Is it idempotent?** It says so in its own header, and the header is not the
thing that makes it true. Every DDL statement in it must be guarded, because the
recovery from a half-applied hand-run is to run it again.

**Did the view survive the copy?** `complaint_overview` is dropped and recreated
here to gain one column. A `drop view` that recreates a *slightly* different view
is the failure mode: nothing errors, and the resident's list quietly loses
`isUnread`, or its overdue rule stops matching the admin's. So the new definition
is diffed line by line against `0031`'s, which is still the latest.

**Is the resident's path untouched?** The one instruction the spec gives that
this file could violate silently.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets.

*Total tests in this file: 13*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_everything_it_builds_on` | Filename order is apply order.  `0031` owns the view this recreates, `20260813100000` owns the `raise_complaint` whose pipeline is mirrored, and `20260820120000` adds the `complaint_events.payload` that `admin_raise_complaint` writes. Sorting before any of them would mean this file's work is undone, or attempted against a column that is not there yet. |
| `test_nothing_later_redeclares_the_view_or_the_function` | Last declaration of a name wins, and this file must be it. |
| `test_every_ddl_statement_is_guarded` | Re-running a hand-applied file must be a no-op.  Each of these is the *only* unguarded form of its statement that this file could plausibly have been written with, which is why they are asserted absent rather than the guarded forms asserted present -- present says a guarded one exists, absent says an unguarded one does not. |
| `test_the_resident_raise_is_not_touched` | The spec's one prohibition. `raise_complaint` keeps the body `20260813100000` gave it, and this file adds a sibling rather than a fork. |
| `test_the_column_defaults_to_the_value_every_existing_row_already_has` | No backfill statement, and none needed: until this file there was no way to raise a complaint other than from the resident portal, so `'resident'` is true of every row that exists. A migration that added the column nullable and then backfilled would have a window in which it was neither. |
| `test_the_ownership_split_is_the_two_lines_the_ruling_names` | The product ruling in one assertion.  `raised_by_membership_id` is the resident when one is named and the admin otherwise; `raised_via` is `'admin'` **only** in the unattached case. Getting the second backwards is the mistake that would put every on-behalf complaint on nobody's resident list -- silently, since the complaint would still exist and the admin portal would still show it. |
| `test_the_raised_event_records_the_admin_as_the_actor` | In both modes. The row says whose complaint it is; the timeline says who acted. Writing the resident's membership there would forge a history entry -- the one thing an append-only timeline exists to prevent. |
| `test_the_pipeline_is_the_one_resident_complaints_already_enter` | Same department resolution, same SLA, same notification fan-out. A second complaint pipeline is how the admin's queue and the resident's start disagreeing about the same complaint. |
| `test_the_new_view_is_0031s_definition_with_one_column_added` | Line by line, both directions.  A `drop view` that recreates a subtly different view raises nothing. Every line of `0031`'s definition must still be here, and the only line this one adds must be the column it was recreated for. |
| `test_the_view_restates_what_dropping_it_took_away` | `drop view` takes the comment and the grant with it -- unlike `create or replace function`, which keeps the oid and therefore keeps both. Losing the grant would make the resident's list a 401 from PostgREST. |
| `test_it_verifies_its_own_work_before_reporting_success` | The house shape for a hand-applied file: five claims, each of which fails the run rather than letting somebody believe it took. |
| `test_the_function_the_backend_calls_is_the_function_that_exists` | The argument names are the RPC contract: PostgREST binds by name, so a rename on either side is a 404 at runtime and nothing at import time. |


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


## `test_blocked_invitee_notice_migration.py`
`20260821170000_blocked_invitee_notice.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It does one thing: it redeclares `claim_staff_invitations` so that the
person whose leadership invitation was refused is told why, on the same
`blocked_at is null` edge that already tells the department.

That is a small change to a function with a large number of properties, and the
properties are the reason this file exists rather than a diff review:

**Is the copy additive?** The body is copied whole from
`20260821140000_leadership_exclusivity.sql` under the house convention
(`20260812113000` 1). "Whole" is checkable: every non-blank line of the applied
version has to still be there. A copy that quietly dropped the already-a-member
skip, the rank derivation or one of the two inserts would not error -- it would
delete a feature from a function that runs on every membership-less sign-in.

**Is the refusal still a skip?** `claim_staff_invitations` runs inside
`resolve_session` and `auth_service._claim_staff_invitations` swallows what it
raises, so a `raise` anywhere in the loop abandons every *other* pending
invitation in the same call, silently. `notify_profile` is a new call inside that
loop, and this is the check that it did not arrive with an exception behind it.

**Does it fire once?** Both notifications must sit inside the same
`blocked_at is null` guard. A blocked person keeps signing in; a message outside
that guard is a message re-sent on every session read.

**Is the wording the wording?** The two sentences were approved by the product
owner on 2026-08-21 and are frozen. They are asserted character for character
here, because the one thing a reviewer cannot see in a 300-line SQL file is a
comma somebody improved.

**Is anything destructive?** Nothing here may delete or alter a row that is not
the invitation being marked.

Whether Postgres accepts the body is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets. The rest is in
`docs/plans/MIGRATION_APPLY_RUNBOOK.md` 15.

*Total tests in this file: 12*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_file_whose_work_it_builds_on` | Filename order is apply order.  `20260821140000` is the constraint that matters: this file copies its `claim_staff_invitations` forward, and sorting before it would restore the version with no invitee notification -- silently, because both files declare the same name and the last one applied wins.  **The check used to be "and it is the last file in the directory", and that became wrong on 2026-08-21** when `20260821200000_departure_continuity.sql` was added -- the same thing that had already happened twice that day, to `test_location_label_migration.py` and then to `test_leadership_exclusivity_migration.py`, and it is answered here the same way. Being last in the directory was never the property; being last *among the files that declare this function* is. The departure-continuity file declares no `claim_staff_invitations` at all, so it cannot undo anything here, and `test_nothing_later_redeclares_the_claim` below is what holds the line for one that ever does. |
| `test_nothing_later_redeclares_the_claim` | The same conditional exemption this file needed from `test_leadership_exclusivity_migration.py`, now owed to the next author.  A later file may redeclare `claim_staff_invitations` -- that is the house convention for changing somebody else's function -- but only by carrying both halves of the announcement forward. One that told the department and dropped the invitee would put the gap this file closed straight back. |
| `test_the_copied_body_is_purely_additive` | The house convention, checked rather than promised.  Every non-blank line of the version `20260821140000` put on the hosted database has to still be present. This is the check that catches a copy made by retyping instead of by extracting -- the already-a-member skip, the rank derivation, both inserts and the claimed-clears-blocked update are all lines that can vanish without anything erroring. |
| `test_the_signature_and_return_type_are_untouched` | `create or replace` cannot change a return type, and would fail on the hosted database if this file tried. It also must not gain a defaulted parameter, which would create an overload rather than replace anything. |
| `test_the_refusal_is_still_a_skip` | The property the whole claim-time design rests on, and the one a new call inside the loop is most likely to break. |
| `test_both_notifications_fire_once_and_on_the_same_edge` | One guard, two `perform`s. Two guards could drift; no guard would re-send the message on every session read a blocked person makes. |
| `test_the_invitee_is_addressed_as_a_person_and_never_as_a_membership` | `notify_profile`, with the claim's own `p_profile_id`.  The recipient may hold no membership at all (a registered provider hired nowhere) or one in a *different* community (the sitting leader). Addressing either through `notify_member` would file the message under a community it is not about, and `20260821140000` 8's feed policy would hide it the day that membership ended. |
| `test_the_two_approved_sentences_are_stored_verbatim` | Frozen product wording, 2026-08-21. Both are one uninterrupted `body` string -- not split across `title` and `body`, which would make the sentence depend on which surface reassembled it. |
| `test_the_payload_names_the_community_and_offers_no_link` | The `url` decision, pinned where it was made.  There is no screen for this: the invitee is not a member of that community, no portal lists invitations addressed to you, and the two blocked populations land in different portals. `notifications_service` renders a missing `url` as `""` and `NotificationBell` then navigates nowhere, which is the house answer -- "a guess about where a notification should land is a worse failure than no link". |
| `test_nothing_is_destructive_and_nothing_else_is_declared` | One function and one counting block. A file this small has no business touching a table, a policy, a trigger or a grant. |
| `test_the_pre_existing_blocked_rows_are_counted_and_left_alone` | `20260821140000` 9's argument at a smaller scale: an invitation blocked before this file was applied has already crossed the edge, and re-arming it would mean writing `blocked_at` backwards. The count goes in the deploy log; nothing is repaired. |


## `test_complaint_engine_v2_repair_migration.py`
Static contracts for the forward-only Complaint Engine v2 repair.

*Total tests in this file: 8*

| Test Function | Description |
|---------------|-------------|
| `test_repair_is_forward_only_and_parses_as_postgresql` | No description provided. |
| `test_manual_window_priority_matches_the_smallint_queue_contract` | No description provided. |
| `test_projector_resolves_each_trigger_row_shape_before_field_access` | No description provided. |
| `test_decline_override_is_internal_and_normal_dispatch_stays_strict` | No description provided. |
| `test_supervisor_picker_can_show_declined_workers_as_excluded` | No description provided. |
| `test_force_assignment_bypasses_the_supervisor_rpc_but_keeps_eligibility` | No description provided. |
| `test_worker_notification_and_postgrest_cache_use_current_main_behavior` | No description provided. |
| `test_repaired_execution_privileges_are_explicit` | No description provided. |


## `test_complaint_engine_v2_supabase.py`
Real-JWT coverage for the repaired Complaint Engine v2 database flow.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_complaint_engine_v2_real_jwt_rpcs_and_triggers` | No description provided. |


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


## `test_departure_continuity_migration.py`
`20260821200000_departure_continuity.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It closes the gap that a supervisor's removal opens: five notification
kinds are addressed to `work_orders.supervisor_membership_id`, and nothing
anywhere re-pointed that column when the person it named stopped being a
supervisor. After the removal those messages are written to an ended membership
and `20260821140000` 8's feed policy hides them, so a department's live jobs
report their progress into a mailbox nobody can open.

The properties worth asserting without a database are these.

**Does it sort last, and does it stay out of the other files' way?** Three
sibling files pin earlier migrations by name. This one must not redeclare
anything they own -- in particular `claim_staff_invitations`, whose fix (product
ruling 8) is Python-side and deliberately not here.

**Is the copy of `notify_complaint_staff` additive?** It is reproduced whole from
`20260812090300` under the house convention (`20260812113000` 1) to gain one
recipient arm. A copy that quietly dropped the admin call, the null-community
guard or the department-manager predicate would not error -- it would delete an
audience.

**Does re-stamping have exactly one target rule?** The trigger and the backfill
both call `department_supervision_successor`, and that is the point of its
existing: two implementations of "who inherits this" would drift, and the drift
would be invisible until somebody compared a live queue against a deploy log.

**Does it move only live work?** A completed or cancelled job needs no
supervisor, and renaming one is falsifying a record rather than repairing it.

**Is anything destructive?** Nothing here may delete a row or drop a column. The
one `drop` is the roster view, recreated in the same file, and the one `update`
is the re-stamp itself.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets. The rest is in
`docs/plans/MIGRATION_APPLY_RUNBOOK.md` 16.

*Total tests in this file: 24*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_file_whose_work_it_builds_on` | Filename order is apply order.  `20260821140000` is the tightest: this file calls `membership_is_live`, which that one declares, and it relies on that file's roster trigger having already settled what a leadership row may be. `0045` matters for the roster view -- sorting before it would mean this file's version is silently replaced by the one with the dead complaint count. |
| `test_it_leaves_the_claim_alone` | Product ruling 8's fix is Python-side, and that is a decision.  `claim_staff_invitations` is the most-rewritten function in this directory and `20260821170000` -- which the owner has in hand and may not have applied when this file goes in -- is its current owner. A redeclaration here would have to guess which generation of that body is on the database, and guessing wrong reverts the invitee notification without erroring. The claim-pass gap is a call site in `auth_service`, so it is fixed at the call site. |
| `test_it_redeclares_nothing_the_sibling_files_pin` | The three static-check files next to this one each guard a name list.  Asserted here as well as there, so the failure names *this* file when it is this file that broke the rule. |
| `test_it_never_writes_the_dead_complaint_column` | Product ruling 1: complaints stay department-pooled.  `complaints.assigned_to_membership_id` is written by exactly one function (`update_complaint`, `0031` 668) and read by nothing. This file re-points *work orders*, which is a different question, and the whole design depends on not answering the other one by accident. |
| `test_the_target_rule_exists_exactly_once` | One function answers "who inherits this", and both callers ask it.  The trigger and the backfill are written months apart in reading order and would be the obvious place for two slightly different orderings to appear. They cannot: neither contains a successor search of its own. |
| `test_the_successor_is_a_live_supervisor_then_the_manager_then_nobody` | The three steps, in that order, and the third one really is "nobody".  A wrong address is worse than a stale one -- the stale one at least names the person the department remembers assigning the job to -- so the search must be able to return null rather than widening until it finds somebody. |
| `test_the_successor_choice_is_deterministic_and_load_aware` | Two supervisors and a coin toss is a re-run of the backfill that moves work around for no reason. The ordering is total: load, then age, then id. |
| `test_only_live_work_is_re_stamped_and_only_within_the_department` | Two scopes, both load-bearing.  A completed job needs no supervisor and rewriting it names somebody who was not there. And a membership can appear on more than one department's work -- an admin membership that raised jobs in two of them -- so re-stamping by membership alone would hand all of it to whichever department lost them first. |
| `test_the_trigger_fires_after_the_write_on_the_columns_removal_touches` | `after`, deliberately.  By then the departing row is already `inactive` in the snapshot the successor search reads, so "a remaining active supervisor" excludes them by construction rather than by an `id <> old.id` a later edit could drop. And the columns are the ones `remove_department_member` writes -- it sets `status` and `rank` in one update, which is one fire and not two. |
| `test_the_trigger_is_what_covers_the_postgrest_bypass` | `staff_assignments_admin_write` is `for all to authenticated` with direct grants (`20260812200000` 26-31), so an admin can flip `status = 'inactive'` without any RPC. That is the fifth removal path and the reason this is a trigger at all -- an edit to `remove_department_member` would cover four.  Checkable statically only as an absence: nothing here may make the re-stamping conditional on having arrived through a function. |
| `test_the_cover_notice_fires_once_on_the_last_supervisor_edge` | Three gates, each for its own reason: the row was a supervisor, the department is one that has a complaint queue, and nobody is left. |
| `test_the_cover_notice_reuses_the_existing_leadership_audience` | With zero supervisors left, `notify_department_leadership`'s audience is exactly "the community's admins plus this department's manager" -- which is precisely the set now covering. A new recipient loop would be a second implementation of a rule `0043` 6 already wrote. |
| `test_the_cover_notice_links_somewhere_that_exists_for_its_reader` | `/admin/complaints`, not `/manager/complaints`.  `frontend/src/features/notifications/portalUrl.js` rewrites the admin path to the manager's for a manager reader, and that module exists precisely because SQL does not know who will read the row. Writing the manager's path here would break it for the admins in the same audience. |
| `test_the_complaint_audience_copy_keeps_every_recipient_it_had` | The house convention, checked rather than promised.  `notify_complaint_staff` is the helper behind six call sites across five migrations, so a recipient lost in this copy is a message lost on every one of them. Each of the three things the original did is asserted present. |
| `test_the_complaint_audience_gains_supervisors_by_roster_rank` | R18, recorded as done in 2026-08-13's ruling table and never implemented.  A supervisor is a rank on a roster row in one department, deliberately (`0043` 386), so no role-based helper can express them. The arm added here is `notify_department_leadership`'s own predicate, narrowed to the complaint's department. |
| `test_nobody_in_the_complaint_audience_is_told_twice` | An admin who also sits on the department's roster as its supervisor satisfies both arms, and being told twice about one complaint reads as a bug in the app (`0043` 416, the same argument one level up). |
| `test_the_roster_view_keeps_every_column_it_had_but_the_dead_one` | The view is dropped and recreated for one column.  A recreated view that is *slightly* different is the failure nobody notices: nothing errors, and a roster tile quietly loses `departureStatus`. So the old column list is read out of `0045` and each name is required to still be there -- except the one being removed. |
| `test_the_new_count_is_a_definer_function_like_its_sibling` | `0043` 245's argument, one column along.  The view is `security_invoker`, so a count computed inline would be filtered by the reader's own RLS on `work_orders` and would under-report for exactly the readers who need it. A number against a roster id the caller already holds leaks nothing. |
| `test_the_python_wire_model_agrees_with_the_view` | The half-landed change this catches: the SQL ships and the repository still asks PostgREST for a column that no longer exists, which is a 400 on every roster read rather than a wrong number. |
| `test_the_backfill_repairs_and_reports_and_refuses_nothing` | The mechanical repair, bounded.  Every removal before this file left its live work orders addressed to an ended membership. Those are repaired to the same rule the trigger uses -- not to a remembered one -- and anything with no successor is counted rather than guessed at. A `raise exception` here would abort an otherwise clean apply over data the file exists to tidy. |
| `test_nothing_is_destructive` | Section 7 repairs an address. It may not remove anything, and the only `drop` in the file is the roster view it recreates two lines later. |
| `test_it_raises_nothing_so_there_is_no_sqlstate_to_map` | A SQLSTATE the API cannot map surfaces as a 500 with a generic message. This file refuses nothing, which is why `pg_errors` is untouched -- asserted rather than assumed, because the check that matters is the same one either way. |
| `test_the_five_notification_kinds_it_exists_for_are_named_somewhere` | Not an assertion about this file's SQL -- it writes none of them -- but about the claim the whole design rests on: these kinds are addressed to `supervisor_membership_id`, so re-pointing that column is what re-points them. If one is ever re-keyed to something else, this fails and somebody re-reads the argument. |


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


## `test_employment_type_repair_migration.py`
`20260817144725_repair_staff_assignment_employment_type.sql` -- what a static
reader can prove about a file that was applied before it was ours.

The file entered this branch from `origin/main` (commit `c0956a2`, 2026-08-17)
byte for byte, because it is **already applied and ledgered** on the hosted
project under exactly this version. Nothing below asks the file to be different;
editing it here would put git and the ledger out of step under one version,
which is the disease issue #41 is about. What the tests ask is the only question
still open: whether the constraint the hosted database now carries admits every
`employment_type` this repository writes.

The hosted `staff_assignments` predates `0001_baseline.sql`. Its hand-built
`staff_assignments_employment_type_check` allowed `internal` and `vendor` only,
while every hiring path in this directory has written `staff` since `0019` gave
the column that default. Worker hiring answered 23514 on every attempt until
this file widened the list (issue #33).

The hazard of an enumerating constraint is a missing word: a value some
migration inserts that the list does not name blocks that insert forever, and
the symptom appears at the first hire rather than at the apply. So the allowed
list is not reviewed here -- it is **derived** from the file's own text, and
every `employment_type` literal any migration writes is required to be a member
of it.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_the_only_ddl_is_the_constraint_swap` | One drop and one add, both naming the same constraint on the same table. A file that is already ledgered on hosted can never be corrected in place, so what it does has to be exactly what its name says. |
| `test_the_allowed_list_is_the_two_legacy_words_plus_staff` | Derived from the file, then compared: the legacy pair the hosted constraint already carried, and the one word the repository writes. |
| `test_every_employment_type_any_migration_writes_is_allowed` | The whole point of the file, held by derivation rather than review.  A value written by some hiring path and missing from the list is a 23514 at that path's first use -- which is exactly how issue #33 was found, on the `staff` this file adds. Order does not enter into it: the inserts live in function bodies and run long after every migration is applied. |
| `test_the_baseline_declares_the_column_with_no_check_of_its_own` | On a fresh database the constraint does not exist until this file makes it. `0001_baseline.sql` declares a bare `text not null`, which is why the repair is a `drop ... if exists` before the add rather than a plain add, and why nothing before 2026-08-17 ever noticed the hosted list was short. |
| `test_it_sorts_after_every_apply_time_declaration_of_the_column` | Filename order is apply order, and only apply-time writes have an order to keep: the column's declaration and the default `0019` sets. Two files that write `staff` (`20260821140000`, `20260821170000`) sort *after* this one and that is correct -- their write is a line of plpgsql inside `claim_staff_invitations`, which runs when a manager claims an invitation, not when the migration is applied. Membership in the allowed list, asserted above, is what protects them; order cannot. |


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


## `test_hosted_invite_claim_names_migration.py`
`20260823150000_hosted_invite_claim_names.sql` -- the name the backend calls
must be a name the database has, on both databases at once.

The hosted project has only `claim_resident_invite(uuid, uuid)`; a fresh one has
only `claim_email_invitation(uuid, uuid)`, from `0001_baseline.sql`. The backend
calls the second name, so every resident email-invite redemption on hosted
answers PGRST202 and the invitee reads "This invite could not be claimed."
(owner probe 2026-08-23, runbook §22 probe (e), §24).

The file creates the missing *name* as a wrapper over the function hosted
already has, under a condition that is false on any database that already has
the name. Three things have to hold for that to be honest, and none of them is
reviewed here -- each is derived:

* the name created is the name the backend's `.rpc(...)` call actually passes,
  read out of `memberships_repository.py`;
* the wrapper's signature, return shape and security posture are
  `0001_baseline.sql`'s, read out of `0001_baseline.sql`;
* the condition cannot fire on a fresh database, because nothing in this
  directory creates `claim_resident_invite` -- which is checked across every
  file rather than asserted.

**Not verifiable statically:** that hosted's `claim_resident_invite` does what
`0001`'s `claim_email_invitation` does. The owner's probe established the
identical signature and return shape `TABLE(membership_id uuid, community_id
uuid, unit_id uuid)`; the bodies are two databases' business and no test here
can see either.

*Total tests in this file: 11*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | The floor: CI replays this directory into an empty database. |
| `test_it_sorts_after_the_file_it_had_to_follow` | Forward-only. A version below the latest on a shared branch is invisible to a fresh replay that has already passed it. |
| `test_the_name_it_creates_is_the_name_the_backend_calls` | The whole point of the file. If the repository is ever rewritten to call `claim_resident_invite` directly this fails, and it should: the wrapper would then be dead weight on hosted and the fresh databases would break. |
| `test_the_wrapper_declares_the_baselines_signature_and_return_shape` | Derived from `0001_baseline.sql`, not typed in. PostgREST resolves an RPC by name *and* argument names, and the service layer unpacks the result by column name, so a wrapper that differs in either is a different function wearing the right name. |
| `test_the_wrapper_keeps_the_baselines_security_posture` | `security definer` with a pinned `search_path`, exactly as `0001` wrote it. A definer function without the pin is the classic search-path escalation, and this one is reachable from an unauthenticated redeem. |
| `test_the_wrapper_keeps_the_baselines_acl` | `0001` revokes from `public, anon, authenticated` and grants only to `service_role`; nothing later in this directory touches that ACL. Only the backend's service client may claim an invite, and creating a second entry point must not be a second door. |
| `test_the_create_is_guarded_on_both_halves_of_the_divergence` | Conditional both ways: the delegate must exist and the wrapper must not. The first half keeps it off a database that has no `claim_resident_invite`; the second makes it idempotent and keeps it from replacing `0001`'s real implementation with a wrapper over a function that is not there. |
| `test_nothing_in_this_directory_creates_the_delegate` | Which is what makes the file a no-op on a fresh database, and it is checked rather than assumed: `claim_resident_invite` is a hosted-only function with no declaration anywhere in this repository, so the guard's first half is false on every database built from these files. |
| `test_the_body_only_delegates` | One statement in the wrapper, and it is a select from the delegate. A wrapper that reimplemented the claim would be the second copy of a transaction this project deliberately has one of. |
| `test_it_creates_nothing_else_and_drops_nothing` | A targeted file, in the shape rule 2 of the migrations README asks for. |
| `test_it_reloads_the_postgrest_schema_cache_last` | A function PostgREST has never seen still answers PGRST202 until the cache turns over, so the fix would look like no fix at all for a while. |


## `test_hosted_request_status_withdrawn_migration.py`
`20260823153000_hosted_request_status_withdrawn.sql` -- a value the
application has always been entitled to write, and one database that never
learned it.

`0001_baseline.sql` declares `access_requests.status` as text with a check
naming four words, `withdrawn` among them. Hosted predates that file and holds
the column as the enum `public.request_status`, whose four labels are
`{pending, approved, rejected, cancelled}` -- probed 2026-08-23, runbook §22
probe (f), §25. So `POST /access-requests/{id}/withdraw` answers 22P02 there and
an applicant cannot take their own request back.

The derivations that make this file honest rather than plausible:

* the label added is the literal the withdraw path actually writes, read out of
  `access_requests_repository.py`;
* that literal is one `0001_baseline.sql`'s own check already allows, so this
  is hosted catching up with the baseline rather than a fifth state being
  invented;
* nothing in this directory creates a type named `request_status`, so the guard
  is false on a fresh database and the file is a no-op there -- checked across
  every file, not assumed.

**Not verifiable statically:** that hosted's enum has exactly the four labels
the probe reported. `add value if not exists` is correct for any superset of
them, and the verification block at the end of the file is the only thing that
can see the real answer.

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_the_file_it_had_to_follow` | Forward-only. A version below the latest on a shared branch is invisible to a fresh replay that has already passed it. |
| `test_the_label_added_is_the_one_the_application_writes` | The defect, stated as a derivation. A file that added some other word would leave the 22P02 exactly where it was. |
| `test_the_label_is_one_the_baseline_check_already_allows` | This is hosted catching up with `0001_baseline.sql`, not a fifth request state being invented. If the two ever disagreed, the fix would belong on whichever side is wrong -- not here. |
| `test_the_baseline_column_is_text_with_a_check_and_no_enum` | Why the file is a no-op on a fresh database, read off the baseline: the column is text, the four words live in a check constraint, and no type of this name is ever created. |
| `test_nothing_in_this_directory_creates_the_enum_type` | The guard's condition, proved false on any database built from these files. `public.request_status` is a pre-baseline artefact of the hosted project and exists nowhere in this repository. |
| `test_the_alter_runs_only_where_the_enum_exists` | Guarded on the type's presence in `pg_type` as an enum (`typtype = 'e'`), not merely on a name being taken -- and executed dynamically, which is what lets the statement be conditional at all. |
| `test_it_adds_and_never_removes_or_retypes` | Widening only. Retyping a live column or dropping the enum would be a table rewrite and a lost guarantee; neither is in the file. |
| `test_the_new_label_is_never_used_as_a_value_in_this_file` | PostgreSQL 12+ allows `add value` inside a transaction block on the one condition that the new label is not *used* until the commit. The file's only other statement reads `pg_enum`, which is a catalogue read and not a use of the value -- so the paste is safe as one transaction. This is the check that keeps it that way. |
| `test_the_verification_is_itself_conditional` | The end-of-file check must not raise on a fresh database, where the type it asks about does not exist. It fires only where the enum is present and the label is still missing. |


## `test_hosted_work_order_drift_migration.py`
`20260822090000_hosted_work_order_column_drift.sql` -- what a static reader
can prove about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a
live database whose `work_orders` table predates `0001_baseline.sql` and
carries hand-built legacy columns the repository has never declared. One of
them (`title`, NOT NULL, no default) rejected every `create_work_order` insert
with SQLSTATE 23502 -- found live on 2026-08-22, when a supervisor's "Raise it"
button answered 422 "Could not raise that job."

The file is a sweep, not a named fix, because `20260820120000` 3 taught the
lesson that these constraints bite one behind the other. A sweep's one real
hazard is its protected list: a repository column wrongly *missing* from that
list would have its NOT NULL dropped on the hosted table, silently weakening a
constraint the repository relies on. So the list is not reviewed here -- it is
**derived** from the declaring migrations' own text and compared exactly.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_file_it_reasons_about` | Filename order is apply order. This file must postdate the last repository declaration it protects and the precedent it cites -- and, as of the day it was written, everything else in the directory. |
| `test_the_protected_list_is_exactly_the_repository_declaration` | The sweep's one real hazard, held by derivation rather than review.  A repository column missing from the list would get its NOT NULL dropped on the hosted table; a name in the list that no migration declares would protect a legacy column and leave the 422 alive behind a passing apply. |
| `test_the_sweep_touches_only_insert_blocking_columns` | Nullable legacy columns, and NOT NULL ones with a default, block no insert and must be left exactly as they are. |
| `test_the_only_ddl_is_the_widening` | One dynamic statement shape, and it can only loosen. `set not null` anywhere here would be the file tightening the very thing it exists to loosen; everything else on the forbidden list is out of scope for a drift reconciliation by definition. |
| `test_the_sweep_reports_and_the_verification_fails` | The sweep may only NOTICE -- an exception there aborts a partial fix into no fix. The verification may only EXCEPTION -- a NOTICE there is the file reporting success it has not checked. Idempotence is the zero-found notice: re-running the file finds nothing and says so. |


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


## `test_issue48_amenity_repro.py`
Repro battery for GitHub issue #48 -- the five amenity defects.

Every test here is expected to FAIL against current code and is marked
``xfail(strict=True)``: the suite stays green while the defect exists, and the
moment a fix lands the test XPASSes, errors the run, and forces its promotion
to a normal test. Nothing in this file repairs anything.

The SQL side is read out of the migration texts the way
``test_migration_directory_is_fresh_appliable.py`` does -- whole-line ``--``
comments stripped first, values extracted by regex -- so each assertion compares
what the database actually accepts against what the Python service actually
sends. The Python side is captured by monkeypatching the repository boundary
and calling the real service functions, never by retyping the payloads here.

Diagnosis key (from the issue-#48 recon):
  D1  catalogue toggle refetches the snapshot three times (frontend twin suite)
  D2  image / opening hours cannot be written or projected
  D3  admin blocks are stored as status='approved' + booking_type='blocked',
      which the status-driven readers cannot see
  D4  status vocabulary drift: phantom 'confirmed'/'blocked' statuses,
      Title-case wire statuses, RPC payload key drift, report KPI key drift
  D5  resident-facing reads route through the admin-guarded snapshot

*Total tests in this file: 12*

| Test Function | Description |
|---------------|-------------|
| `test_timeline_filter_statuses_exist_in_the_enum` | No description provided. |
| `test_approved_filter_values_exist_in_the_series_vocabulary` | No description provided. |
| `test_service_booking_types_pass_the_check_constraint` | No description provided. |
| `test_record_payment_sends_keys_the_rpc_reads` | No description provided. |
| `test_add_charge_sends_keys_the_rpc_reads` | No description provided. |
| `test_report_filters_send_keys_the_rpc_reads` | No description provided. |
| `test_refund_rpc_does_not_require_a_key_python_never_sends` | No description provided. |
| `test_report_kpi_keys_cover_what_build_report_reads` | No description provided. |
| `test_a_block_as_stored_paints_blocked_on_the_timeline` | No description provided. |
| `test_wire_status_is_a_lowercase_machine_value` | No description provided. |
| `test_amenity_write_accepts_image_and_hours` | No description provided. |
| `test_snapshot_amenity_projection_carries_image_and_hours` | No description provided. |


## `test_leadership_exclusivity_migration.py`
`20260821140000_leadership_exclusivity.sql` -- what only a static reader can
check about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a
live database. It installs two triggers, rewrites six functions it does not own,
adds two columns and replaces three RLS policies -- and every one of those is
load-bearing for a rule the product owner froze on 2026-08-21:

    RULING 1  leadership is invite-only and never from the marketplace pool
    RULING 2  leadership is exclusive to one community
    RULING 3  removal severs access completely

So the questions worth asking without a database are these.

**Does it parse, and does it sort last?** A migration that lands before the file
owning a function it rewrites is silently undone. `20260821113000` (the
location-picker work) is the tightest constraint: this file copies
`register_service_provider` forward, and copying it forward is only correct if
this file wins.

**Did the copied bodies survive?** Five functions are reproduced whole to gain a
guard each -- the convention `20260812113000` set. A copy that quietly dropped
`p_location_label`, or the already-a-member skip in the claim, or the
separate-account refusal in registration, would not error. It would delete a
feature.

**Is the claim's refusal a skip rather than a raise?** This is the design
decision the charter asked to be recorded, and it is visible in the SQL: the
blocked branch ends in `continue`, and there is no `raise` anywhere between the
loop's `for` and its `end loop` that a blocked invitation reaches. A `raise`
there would be swallowed by `_claim_staff_invitations` and would abandon every
other pending invitation in the same call, silently.

**Do the errcodes exist in Python?** A SQLSTATE the API cannot map surfaces as a
500 with a generic message, which is precisely the outcome custom SQLSTATEs
exist to prevent.

**Is anything destructive?** Nothing here may delete a row. Both memberships and
provider profiles are somebody's account, and section 9 of the file argues at
length that repairing them is not a migration's decision.

*Total tests in this file: 20*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_file_whose_work_it_rewrites` | Filename order is apply order.  ``20260821113000`` is the one that matters most and the one most recently added: it put ``p_location_label`` on ``register_service_provider``, and this file copies that signature forward. Sorting before it would restore the seven-argument version and break the location picker. |
| `test_nothing_later_redeclares_what_this_file_owns` | Last declaration of a name wins, and this file's *claim-time work* must survive.  The check the name suggests -- nobody may ever redeclare these nine -- is stricter than the property that matters, and it became wrong on 2026-08-21 when `20260821170000_blocked_invitee_notice.sql` added the invitee's half of the blocked-invitation announcement. That file redeclares `claim_staff_invitations` deliberately and copies this one's body whole, which is the house convention (`20260812113000` 1: "the body below was extracted mechanically from that file, so the starting point is provably the applied text"). `test_location_label_migration.py` had the same thing happen to it a few hours earlier, and answered it the same way.  So `claim_staff_invitations` is exempted **conditionally**: a later declaration of it is a clash unless it carries every claim-time semantic this file established -- the skip, the two blocked columns, the edge guard and the department notification. A file that reverted the refusal to a `raise`, or dropped the department's message while adding somebody else's, would still fail here, which is the accident this test exists to catch. The other eight names remain nobody's to redeclare. |
| `test_every_ddl_statement_is_guarded` | Re-running a hand-applied file must be a no-op.  The recovery from a half-applied hand-run is to run the file again, so every statement has to tolerate its own effect already being present. |
| `test_nothing_is_destructive` | Section 9's argument, enforced rather than promised.  An account holding two leaderships, or a leadership and a provider profile, is somebody's job and somebody's livelihood. Which one they keep is not a question this file may answer, so it counts them into a `notice` and touches nothing. |
| `test_the_roster_trigger_fires_before_the_write_on_the_right_columns` | A trigger that fires `after` cannot refuse, and one that watches the wrong columns does not fire when the rank changes. |
| `test_the_roster_trigger_refuses_both_rulings_with_distinct_codes` | One trigger, two answers.  Collapsing them into one code would leave a client unable to offer "hire them at technician rank" for one and "wait until they leave" for the other. |
| `test_the_provider_trigger_closes_the_same_door_from_the_other_side` | No description provided. |
| `test_the_leadership_predicate_asks_all_three_active_conditions` | It has to agree with `can_supervise_department`, which one policy asks beside it. A predicate that said somebody leads while the authorisation predicate said they do not is a hole in one direction or a lockout in the other. |
| `test_registration_keeps_the_location_label_and_the_older_refusal` | Two features this copy could have deleted without erroring.  ``p_location_label`` is 2026-08-21's location-picker work, and the separate-account refusal is 2026-08-12's. Both live in the body being copied forward, and both are invisible in a diff that only reads the new lines. |
| `test_the_claim_keeps_every_rule_it_already_had` | No description provided. |
| `test_the_claim_skips_rather_than_raises` | The claim-time refusal design, asserted where it is decided.  ``claim_staff_invitations`` runs inside ``resolve_session`` on every membership-less session read, and ``_claim_staff_invitations`` (``auth_service.py``) swallows whatever it raises. So a refusal spelled as an exception would not refuse *this* invitation, it would abandon the whole call -- including any legitimate invitation later in the same loop -- and it would do it silently, on a screen that looks fine. |
| `test_the_invitation_refuses_early_and_still_refuses_the_old_collisions` | No description provided. |
| `test_the_invitation_read_carries_the_new_columns` | No description provided. |
| `test_the_ownership_predicate_now_asks_whether_the_row_is_live` | `is_own_staff_assignment` is the predicate behind the worker calendar, the job list, leave, availability, every work order the caller was ever assigned, their old departures and their old gate rota. It had no time condition at all, so a removed worker satisfied it forever. |
| `test_the_mailbox_policies_ask_for_an_active_membership` | `0046`'s policies were keyed on the participant columns alone, so a removed supervisor kept reading every community-A thread forever -- including the manager's side of their own departure. |
| `test_the_feed_policy_asks_whether_the_membership_is_still_live` | No description provided. |
| `test_the_farewell_notification_survives_the_feed_scoping` | The trap in section 8, closed in section 8.  ``remove_department_member`` ends the membership and *then* tells the person they were removed, keyed to the membership it just ended. Under the policy alone that message would be written and instantly invisible -- the one notification a removed person most needs, lost to the rule meant to protect them. |
| `test_every_custom_sqlstate_this_file_raises_is_mapped_in_python` | An unmapped SQLSTATE is a 500 with a generic message, which is exactly what custom codes exist to prevent. This catches the half-landed change where the SQL ships and ``pg_errors`` does not. |
| `test_the_two_new_codes_are_conflicts_and_are_distinguishable` | No description provided. |


## `test_leadership_stale_access.py`
Ruling 3 on the one read the BFF composes itself.

    "Once a supervisor/manager is removed from a community and later invited to
    a different one, they must not be able to see ANYTHING from the old
    community." -- product owner, 2026-08-21.

Almost every read that ruling covers is decided in Postgres: the calendar and
job list through ``is_own_staff_assignment``, the complaint queue through
``can_supervise_department``, the mailbox and the feed through RLS policies.
None of those is reachable without a database, and all of them are asserted
statically in ``test_leadership_exclusivity_migration.py``.

``list_engagements_for_profile`` is the exception. It is four plain PostgREST
reads stitched together in Python -- and it is the *only* read that can see a
provisioned manager or supervisor at all, because leadership holds no
``service_providers`` row and every provider-keyed path is blind to it. It fills
``communities[]`` on the worker snapshot, which is where the supervisor's
Complaints screen finds a department to ask about. If it returned the ended
community-A engagement, the removed supervisor would be looking at community A's
name on their own dashboard.

So the filters are asserted where they are written, against a fake client that
records what was asked rather than what came back. Asserting the *rows* would
pass just as well against a repository with no filters at all and a fixture that
happens to contain only live ones.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_the_membership_read_asks_only_for_live_memberships` | ``status = 'active'`` **and** ``ended_at is null``, both.  They are not the same question. ``0043``'s ``remove_department_member`` writes both, but the baseline's older paths set one or the other, and a read that asked for only the first would admit a membership somebody ended without restatusing it. |
| `test_the_roster_read_asks_only_for_live_assignments_by_default` | ``active_only`` defaults to True, and the snapshot leaves it there.  The parameter exists for a "communities I have worked in" screen that has never been built. The default is what ruling 3 rides on, so the default is what is pinned. |
| `test_an_account_with_no_live_membership_gets_nothing_at_all` | A supervisor removed from A and not yet invited anywhere.  The short-circuit matters: without it the roster read would run with an empty ``in_`` list, and an empty ``in`` is a filter that matches nothing on PostgREST but is a filter this code would rather not depend on. |
| `test_the_engagement_that_survives_is_the_live_one` | No description provided. |


## `test_location_label_migration.py`
`20260821113000_location_labels.sql` -- what a hand-applied file cannot be
allowed to get wrong.

This migration is pasted into the Supabase SQL editor by a person, once, against
a live database. Nothing in this repository runs it first. It is also the most
dangerous shape a migration takes here: **four functions and two views are
dropped and rewritten whole** to gain one column each, and every one of them is
load-bearing for a different screen. So the checks a static reader can make are
worth more than usual, and they are these:

**Is it idempotent?** Its own header says so, and a header is not what makes it
true. The recovery from a half-applied hand-run is to run the file again.

**Is every old signature actually gone?** Three functions gain a parameter.
`create or replace` cannot add one -- a defaulted parameter creates an
*overload*, after which every existing PostgREST call is "function is not
unique" and fails. The drop has to name the old signature exactly, so the drops
here are diffed against the signatures the previous migrations declared.

**Did the bodies survive the copy?** `search_hireable_service_providers` is
rewritten to add one returned column. A rewrite that quietly changes a radius
predicate or an `order by` would not error; it would change who gets hired.
Every predicate that decides *which* people come back is asserted to have been
carried over character for character.

**Did the coordinates stay out of the hiring read?** The whole feature is a
label on a card that deliberately withholds a home coordinate. A file that adds
`p.latitude` while it is in there widening the same function is the way that
protection dies.

Whether Postgres accepts the bodies is a question only Postgres answers;
`pglast` parsing it is as close as this suite gets.

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_every_file_whose_work_it_rewrites` | Filename order is apply order.  `0034` owns `service_provider_overview`, `0045` owns the current `upsert_service_provider`, `20260811162409` owns `register_service_provider`, `set_my_community_location`, `create_founder_community` and `community_settings_overview`, and `20260812090100` owns the hiring search. Sorting before any of them would mean this file's work is silently undone by the older definition. |
| `test_nothing_later_redeclares_what_this_file_owns` | Last declaration of a name wins, and this file's *label work* must survive.  The check the name suggests -- nobody may ever redeclare these seven -- is stricter than the property that matters, and it became wrong on 2026-08-21 when `20260821140000_leadership_exclusivity.sql` added a leadership refusal to `register_service_provider`. That file redeclares the name deliberately and copies this one's body whole, which is the house convention (`20260812113000` 1: "the body below was extracted mechanically from that file, so the starting point is provably the applied text").  So the assertion is the real invariant instead: a later redeclaration is a clash **unless it carries the label parameter forward**. A file that reverted to the seven-argument signature would still fail here, which is the accident this test exists to catch. |
| `test_every_ddl_statement_is_guarded` | Re-running a hand-applied file must be a no-op.  The unguarded forms are asserted *absent* rather than the guarded ones asserted present: present only says a guarded statement exists somewhere, absent says an unguarded one does not. |
| `test_each_changed_function_is_dropped_by_the_signature_it_actually_has` | The overload trap, asserted against the previous files rather than a remembered list.  Adding a defaulted parameter with `create or replace` leaves *two* functions of that name, and PostgREST then fails every call with "function is not unique". The drop must therefore name the exact argument list the earlier migration declared -- so each expected drop below is built from the file that owns the old definition, not typed out here. |
| `test_the_hiring_search_gains_a_label_and_still_returns_no_coordinates` | The point of the whole feature, and the line it must not cross.  `_CANDIDATE_SELECT` in the repository withholds `latitude`/`longitude` from every hiring read. This function is the other half of that promise, and it is being rewritten here -- which is exactly when a coordinate would slip in. |
| `test_the_rules_that_decide_who_is_hireable_are_carried_over_unchanged` | Distance mechanics are not this file's business.  Every predicate that decides *which* providers come back, and the ordering that decides in what order, is compared against the definition `20260812090100` left behind. A rewrite that dropped a `not exists` would offer a manager somebody they had blacklisted, and nothing would error. |
| `test_the_provider_overview_keeps_every_column_it_had` | The view is dropped and recreated for one column.  A recreated view that is *slightly* different is the failure mode nobody notices: nothing errors, and a profile screen quietly loses `communityCount` or `skillNames`. So the old column list is read out of `0034` and each name is required to still be there. |
| `test_the_stored_cap_is_the_one_the_wire_model_truncates_to` | 120 characters is a privacy boundary, not a storage decision -- long enough for "suburb, city, state" and too short for a street address.  The number lives in two places by necessity (a `check` constraint and the label builder that must not emit one the constraint would refuse), so the two are compared rather than trusted. |
| `test_nothing_here_touches_a_distance_function_or_a_generated_column` | The one prohibition the change carried from the start: input quality only.  `location` stays generated from `latitude`/`longitude`, and `search_serviceable_communities` -- the provider's own side of the same proximity maths -- is not mentioned at all. |


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


## `test_migration_directory_is_fresh_appliable.py`
`backend/supabase/migrations/` as a whole -- can a database that has never
seen this project apply the directory from the top?

**This is the first suite in this repository whose subject is the directory
rather than one file.** Every other `test_*_migration.py` pins one migration and
sweeps its siblings only to prove nothing later overrides it. Nothing has ever
asked whether the set, replayed from empty, still lands -- which is how issue
#41 happened: `20260818141040_remote_schema.sql`, a 9,831-line
`supabase db diff` snapshot, was committed to `origin/main` as a migration. It
fails a fresh apply at the first generated-column `ALTER`, and on the way there
it recreates a legacy sentinel table, drops two SSE triggers without recreating
them, and swaps RLS policies. CI's `database-browser` job is the thing that
replays this directory into an empty database, so a file like that stops every
branch, not just its own. (The version carries a row in the hosted ledger --
probed 2026-08-23 -- so the file could not simply be deleted; it survives as a
comment-only tombstone, which this suite is blind to because every check below
strips whole-line `--` comments first. Runbook section 22.)

**Every SQL pattern here is case-insensitive, and that is the point of the
file.**
`supabase db diff` writes uppercase SQL. The repository's hand-written
migrations are lowercase, so are the pins that guard them, and an uppercase
`CREATE TABLE "public"."visitor_access_requests"` is invisible to every one of
them. The hazard did not slip past a weak rule; it slipped past a rule that
could not see it.

The expected sets are derived from the migration texts and from the application
code they protect, not typed in from a reviewer's notes. The one exception is
the retired-table list in `test_no_migration_recreates_a_retired_table`, which
names twenty tables that no longer exist anywhere to be derived from -- it cites
the commits that removed them instead.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_every_migration_parses_as_postgresql` | (a) The floor. A file that does not parse cannot apply, and the whole directory is replayed into an empty database by CI's `database-browser` job on every push. |
| `test_no_migration_alters_a_generated_column_or_one_it_depends_on` | (b) The statement `20260818141040_remote_schema.sql` dies on, at its own line 1314.  Postgres refuses `set default` on a generated column and refuses `set data type` on any column a generated expression reads. A `db diff` snapshot emits both, because it re-states every column of every table it saw. Both sides are derived: the generated columns from the `generated always as (...) stored` declarations, the columns they depend on from the identifiers inside those expressions. |
| `test_no_migration_creates_the_legacy_sentinel_table` | (c) `schema_generation()` decides which schema the backend is talking to by asking whether one table exists. Create that table in a migration and every fresh database reports itself as the pre-baseline legacy schema, and the dashboard reads projections that were never built for it.  The name is read out of `dashboard_repository.py` rather than typed here, so this test tracks the code it protects: if the probe ever changes table, the guard follows it instead of quietly protecting the wrong name. |
| `test_no_migration_drops_a_trigger_the_directory_never_recreates` | (d) The `db diff` snapshot drops `dashboard_sse_amenity_bookings` and `dashboard_sse_visitor_requests` and recreates neither, so the dashboard's realtime feed goes silent with nothing in the apply output to say so.  Recreation is looked for across the whole directory, not just the dropping file, because `0045` legitimately re-lays two of `0043`'s triggers. The dynamic `dashboard_sse_%I` loops are expanded from their own table arrays. |
| `test_every_unguarded_drop_is_followed_by_its_own_recreation` | (e) A `drop policy` or `drop constraint` that neither says `if exists` nor puts the object back is a silent removal: the apply succeeds and the rule the repository thought it had is gone. That is how the `db diff` snapshot swaps RLS policies -- it drops names `0033` and `0043` created and re-adds its own reading of them, or nothing at all.  Only names the directory itself creates are in scope; a hand-applied file may legitimately drop a hosted-only legacy object it did not make. The five unguarded drops here are all inside `if exists (select 1 from pg_constraint ...)` blocks and all re-add the same name a few lines later, which is the other way to be safe. |
| `test_no_migration_recreates_a_retired_table` | (f) Twenty tables were deleted from this project's schema by `origin/main` @ `94556e5` and `76e1b15`, the pair of commits that replaced `0001_init.sql`/`0002_rls.sql`/`0003_access_token_hook.sql` with `0001_baseline.sql`. Nothing in the repository declares them any more, so unlike every other check in this file the list cannot be derived -- it is written out, with its provenance, and it is the one hardcoded set here.  A `db diff` snapshot taken against a database whose history includes them brings them back, and a fresh database then carries tables the code reads only in its `legacy=True` branch.  Three tracked migrations **rename** a pre-baseline table into this namespace -- `0023` parks four `amenity_*` tables as `legacy_*`, `0030` renames `notifications`, `0032` renames `visitor_events`. Those renames are house-approved and conditional, and only `create table` is checked here so that they cannot trip it. |


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


## `test_nearby_community_search_migration.py`
No description provided.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_nearby_search_keeps_nearby_communities_without_open_matching_work` | No description provided. |


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

*Total tests in this file: 12*

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
| `test_the_python_mirror_matches_the_javascript_rule_table` | A second implementation is only safe while it is checked against the first. The four rules are read out of `portalUrl.js` by name rather than by behaviour -- enough to fail loudly if somebody adds a fifth here and not there, or renames one.  **The sub-screen list is compared by content**, not by name. Naming was enough while the list was three entries nobody touched; `work-orders` joined it on 2026-08-12 for the work-order notification repoint, and a name check would have passed just as happily with the JavaScript half of that change reverted -- leaving every one of the seven links bouncing a department manager home while this file asserted they were fine.  **And per portal, since 2026-08-21.** The comparison is now dictionary against dictionary rather than tuple against tuple, which keeps that property under the restructure: reverting the JavaScript to one shared list, or quietly handing `worker` the manager's four sub-screens, changes the parsed table and fails here. A comparison that had flattened both sides back into one set of names would have lost exactly the teeth the paragraph above is about. |
| `test_a_notification_lands_somewhere_its_reader_may_go[manager]` | Renamed on 2026-08-21: it said `a_managers_` and `worker` is not one.  A supervisor is the reader this parametrisation was extended for, and the name would have been a small lie of exactly the kind the rest of this file spends its comments correcting. |
| `test_a_notification_lands_somewhere_its_reader_may_go[security-manager]` | Renamed on 2026-08-21: it said `a_managers_` and `worker` is not one.  A supervisor is the reader this parametrisation was extended for, and the name would have been a small lie of exactly the kind the rest of this file spends its comments correcting. |
| `test_a_notification_lands_somewhere_its_reader_may_go[worker]` | Renamed on 2026-08-21: it said `a_managers_` and `worker` is not one.  A supervisor is the reader this parametrisation was extended for, and the name would have been a small lie of exactly the kind the rest of this file spends its comments correcting. |


## `test_open_jobs_board_migration.py`
Static contracts for the open-jobs board migration.

The rulings of 2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §22) and the
orchestrator's adjudications D1-D7 (`docs/plans/OPEN_JOBS_BOARD_SPEC.md`) are
promises about SQL that no fixture-backed API test can see. Same idiom as
``test_complaint_engine_v2_repair_migration.py``: parse the file, then pin the
clauses the spec froze -- so a later edit that quietly relaxes "open", forks
the trade rule, or narrows the projection trigger back down fails here first.

*Total tests in this file: 11*

| Test Function | Description |
|---------------|-------------|
| `test_board_sorts_after_the_hosted_high_water_mark_and_parses` | No description provided. |
| `test_the_board_read_is_definer_keyed_on_the_caller_alone` | RLS correctly hides unheld jobs from workers, so the board must be SECURITY DEFINER with identity from auth.uid() and no arguments a caller could widen. |
| `test_open_means_uncommitted_and_unpromised_in_both_functions` | D1, stated twice on purpose: status alone cannot define open, because create_work_order writes `offered` with no assignment rows at all. |
| `test_the_trade_rule_is_the_engines_own_clause_in_both_functions` | D2: the short-circuit for provider-less roster rows is deliberate -- it is dispatch_candidates' rule, and a different one here would fork eligibility. |
| `test_exclusion_filters_the_board_and_guards_the_claim` | D7 on the read, D2 on the write: the list and the click are seconds apart, so the claim re-checks what the board already hid. |
| `test_the_claim_locks_first_and_skips_slot_checks_without_a_slot` | The race is settled on the `for update` line, as it is on accept; and ruling C3 means the overlap refusal runs only when the job has a slot -- none of the slot-dependent checks can run without one. |
| `test_the_claimed_row_takes_the_accept_paths_exact_shape` | D3: accepted, not forced, not auto-assigned, slot copied from the job (which may be null), the job moved to `scheduled` -- the shape force_assign_work_order already established for scheduled+null-slot. |
| `test_no_new_event_word_the_payload_carries_the_distinction` | D4: a new complaint-event word costs a constraint drop-and-recreate (runbook §19 rule); `claimed: true` inside `job_assigned` does not. |
| `test_the_supervisor_hears_claimed_and_not_their_own_echo` | D6: the resident's notification is accept's own; the supervisor's is the new `work_order.claimed` kind with a supplied title, skipped when the claimer IS that supervisor. |
| `test_the_projection_trigger_treats_an_accepted_insert_as_acknowledged` | D5: on the offer path the complaint moved open -> acknowledged when the offer was inserted; a claim inserts `accepted` directly, and without this widening the complaint would sit at `open` with a committed job. |
| `test_execution_privileges_are_explicit_and_the_cache_is_reloaded` | No description provided. |


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

*Total tests in this file: 44*

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
| `test_the_snapshot_always_carries_the_four_weekly_new_counts` | The frontend replaces its hardcoded '+2 this week' chips with exactly this object, so the field name and its four keys are load-bearing. |
| `test_weekly_new_defaults_to_zeroes_never_to_absence` | `0` when nothing was created; the key itself must never be missing. |
| `test_the_visitor_projection_reads_the_table_residents_write` | One source, on every schema generation. Reading `visitor_access_requests` was reading the empty half of a split brain: the rows are in `visitor_requests` and have been since `0032`. |
| `test_the_visitor_projection_takes_no_schema_generation_argument` | The branch is gone, not defaulted. A `legacy=` keyword left in place would let a caller reintroduce the pre-baseline read by passing True. |
| `test_the_booking_projection_reads_amenity_bookings_not_the_series_tables` | `0023` moved the booking RPCs onto `amenity_bookings` and parked the old tables under `legacy_` names. Nothing has written a series row since -- hosted holds none -- so the two-query series read answered 0 forever. |
| `test_the_service_reads_events_from_the_key_the_projection_embeds` | The repository's embed key and the service's `.get` must move together; this is the pair that drifted apart when `0032` took the old name. |
| `test_the_visitor_card_keeps_every_key_the_frozen_shape_promises` | Collapsing the branch must not move the wire contract by one key. The window comes from `valid_from`/`valid_until` now, and nothing else about the card changes. |
| `test_the_booking_row_keeps_every_key_the_frozen_shape_promises` | `bookingGroupId` was the series id on the legacy arm and is the row's own id now, because `amenity_bookings` has no series above it. `cancellationReason` stays in the payload as `None` -- the key is part of the contract even where the column is not. |
| `test_weekly_new_counts_ask_the_tables_residents_write` | Head-only counts, filtered to the window -- and pointed at the tables the rows are actually in. Counting `visitor_access_requests` and `legacy_amenity_booking_series` made both chips read `+0 this week` on a project where requests were arriving. |
| `test_weekly_new_counts_on_an_executor_ask_the_same_four_tables` | The snapshot hands its pool down so the counts join the concurrent batch; the executor path must be the sequential path, only faster. |
| `test_the_snapshot_assembles_correctly_when_reads_finish_out_of_order` | The earliest-submitted reads finish last here, so any assembly that depended on completion order (rather than on which future is which) would scramble the payload. |
| `test_a_failing_read_fails_the_snapshot_with_its_own_exception` | Concurrency must not soften errors into a partial payload: the read's own exception type propagates, exactly as it did sequentially. |


## `test_registration_contracts.py`
No description provided.

*Total tests in this file: 23*

| Test Function | Description |
|---------------|-------------|
| `test_google_and_email_password_are_supported_configured_methods` | No description provided. |
| `test_establishing_a_session_clears_the_preauth_csrf_cookie[establish_session-extra0]` | No description provided. |
| `test_establishing_a_session_clears_the_preauth_csrf_cookie[establish_recovery_session-extra1]` | No description provided. |
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


## `test_resident_capability.py`
The resident capability, which is a residency and not a role.

`require_membership_role("resident")` guarded the resident verbs -- cancel work,
reopen, confirm a resolution, answer a proposed visit -- and refused them to the
admin who owns flat B-402. That was never a policy anybody chose. One
`community_memberships` row exists per person per community
(`memberships_active_person_community`, `0001_baseline.sql:45`), so the person
who both runs the association and lives in it has exactly one membership and its
role says `admin`; the fact that they are also a resident lives in
`unit_residencies` and nowhere else.

`require_resident_capability` asks `unit_residencies`. These tests pin the three
things that makes true and the two it must not change:

1. `resident` passes with **no query at all** -- the guard runs on every one of
   these routes and the common caller must not pay for the uncommon one.
2. Any other role passes if and only if an active residency row exists.
3. The query is the one the session layer already runs
   (`app/services/auth_service.py:463-471`): `unit_residencies`, membership
   equality, `ended_at is null`, one row.
4. The refusal is byte-identical to the role guard's -- same message, same
   `community_role_required` code. Widening who passes must not be a wire change.
5. It still refuses staff who live nowhere, which is the whole reason the routes
   are guarded.

*Total tests in this file: 7*

| Test Function | Description |
|---------------|-------------|
| `test_a_resident_passes_without_a_single_query` | The role is already the answer, and this guard sits on every resident write in the product. A round trip that could only ever confirm what the role column already said is a round trip on every one of them. |
| `test_an_admin_who_lives_here_passes` | The reason this exists. An admin with a flat is the resident of that flat, and the role column was never where that fact was recorded. |
| `test_an_admin_who_lives_nowhere_is_refused` | The guard is not a licence for staff. An association secretary who lives across town still may not confirm a resolution on somebody's home; the admin portal's own raise endpoint is where their complaints go. |
| `test_the_refusal_is_identical_to_the_role_guard_s` | Widening who passes is not a wire change. Every client that already handles the resident 403 must keep handling this one, so the two refusals are compared to each other rather than to a literal. |
| `test_the_lookup_is_the_one_the_session_layer_already_runs` | `unit_residencies`, this membership, `ended_at is null`, one row. Two places answering "is this person resident here" must not be able to disagree, and `ended_at is null` is also the predicate the partial unique index `residencies_active_member_unit` is built on. |
| `test_one_query_and_not_two` | The guard runs on every write it protects, so a duplicated read here is a duplicated read on all of them. |
| `test_a_past_tenant_is_not_a_resident` | The row is filtered in the database, so "moved out" arrives here as no rows. Pinned because a guard that read the residencies and then decided in Python is one refactor away from forgetting the `ended_at` test. |


## `test_resident_sets_the_time_migration.py`
Static contracts for the resident-scheduling migration.

The product rulings of 2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §23, F1-F3)
and the orchestrator's adjudications G1-G11
(`docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`) are promises about SQL that no
fixture-backed API test can see -- this file is hand-applied and there is no
database in the suite. Same idiom as `test_open_jobs_board_migration.py`: parse
the file, then pin the clauses the spec froze.

**The pins that carry the most weight are the negative ones.** Three of the
decisions here are decisions *not* to add something -- no new work-order status,
no new complaint-event word, no change to the board predicate -- and each of
them is one careless edit away from a constraint rebuild on a hosted database.
The other three are the redefinitions: `sync_dispatch_tasks` and
`fire_dispatch_task` are re-issued whole, and a `create or replace` that quietly
loses an arm is a timer that stops firing with nothing in the apply output to
say so.

*Total tests in this file: 26*

| Test Function | Description |
|---------------|-------------|
| `test_it_sorts_after_the_file_it_had_to_follow_and_parses` | Forward-only, and named: this file must land after the open-jobs board, whose `project_complaint_from_jobs` and board predicate it reads and does not replace. |
| `test_it_is_the_last_word_on_every_function_it_redefines` | Not "it is last in the directory". The property is being last *among the files that declare each function*, which is what decides which body the database ends up holding. |
| `test_the_only_constraint_it_touches_is_the_dispatch_task_kind` | G2 and the no-new-word rule, stated as an absence. `work_orders` gets no new status and `complaint_events` no new type -- both are closed lists on live tables, and both refusals are what the payload discriminators exist for. |
| `test_the_widened_kind_list_keeps_every_word_it_already_had` | Widening only. The old list is derived from `20260813104000`'s own text rather than reviewed by eye, so a word dropped in the copy fails here. |
| `test_no_new_status_word_reaches_the_work_order_table` | Pick-mode is `awaiting_resident` with a NULL slot and nothing else. A status this file invented would be an insert the CHECK refuses at apply time on any database with rows. |
| `test_the_board_predicate_is_not_touched` | G8: `awaiting_resident` was already off the board, and drafts stay claimable -- including a facility draft inside the courtesy gate, where the claim simply wins and the task no-ops. |
| `test_the_slot_finder_never_probes_by_writing_a_trial_hour` | Six triggers fire on `work_orders` writes, so a finder that stored a candidate hour to ask about it would fire all six per probe. The whole refactor exists to make that unnecessary. |
| `test_the_finder_uses_the_frozen_duration_step_and_horizon` | G10: hardcoded in the engine's style, like the 24-hour deadline. Two-hour visits, top-of-hour candidate starts, fourteen days of looking. |
| `test_the_three_argument_candidates_became_a_delegate_not_a_fork` | One eligibility rule, one ordering, one set of grants. A second copy would be a second answer to "who may take this job", and the one that drifts is always the one nobody is testing. |
| `test_a_slotless_resident_raise_becomes_a_request_to_pick` | Ruling F1. A resident-subject job is `awaiting_resident` either way, and the slot is the discriminator; the deadline arms in both modes, because silence is answered in both. |
| `test_a_slotless_facility_raise_stays_a_draft_and_enqueues_nothing_here` | The trigger arms the task from the status alone -- the rule `0037` §2 set and every handler since has kept. A `create_work_order` that enqueued by hand would arm it twice on any path that also changes the status. |
| `test_the_residents_pick_checks_ownership_mode_and_the_hour_in_that_order` | The guard order is the contract: a stranger is refused before they learn anything about the job, and the mode refusal comes before the hour is even looked at. |
| `test_the_residents_pick_moves_the_job_to_the_open_pile` | "Only when they set it does the job reach the open pile" (F1). `offered` is that pile: it arms the existing `manual_window` machinery through the trigger and puts the job on the open-jobs board. |
| `test_pick_mode_has_no_decline` | Ruling F3. There was never a proposal, so there is nothing to refuse; the decline stays on `respond_to_work_order_schedule`, which this file does not touch. |
| `test_the_timeout_branches_on_the_slot_and_keeps_the_old_arm_intact` | Approve-mode is untouched: a proposed hour nobody answered still proceeds to `offered`, with the same event and the same notification. |
| `test_an_expired_pick_is_booked_and_assigned_without_a_new_event_word` | Ruling F2, and the no-new-word rule: `job_assigned` carries `auto_assigned: true`, exactly as the board's claim carries `claimed`. |
| `test_nobody_free_inside_the_horizon_returns_the_job_to_the_board` | A job stranded in `awaiting_resident` with a dead timer is invisible to everybody. `draft` is claimable (C3), and the supervisor is told rather than left to notice. |
| `test_the_facility_handler_bails_on_anything_a_human_already_moved` | Idempotent, because a task may fire more than once (`0037`'s lease) and because a board claim can win the race -- which is the outcome this task exists to make unnecessary, not one to fight. |
| `test_the_courtesy_gate_is_urgent_resident_jobs_with_nobody_on_them` | "Only after all urgent resident complaints in the department have been allotted" (F1). Allotted is asked the way the board asks it: a live offer or an acceptance. |
| `test_the_trigger_arms_the_new_task_and_keeps_every_arm_it_had` | `sync_dispatch_tasks` is re-issued whole, so every arm has to be re-proved. The final `else` still cancels timers on a status this function does not recognise -- `draft` simply stopped being one of those. |
| `test_the_handler_table_gains_one_arm_and_loses_none` | `fire_dispatch_task`'s `else` silently swallows a kind nothing handles, so a missing arm is a task that completes with an error nobody reads. |
| `test_the_snapshot_gains_a_bucket_and_narrows_open_requests` | A job waiting on a resident is not an open request: nothing on it is the supervisor's to move. The narrowing is the other half of the change and is the part that would go unnoticed -- the new section would fill and the old one would keep double-counting. |
| `test_the_python_wire_model_agrees_with_the_new_snapshot` | The half-landed change this catches: the SQL ships and the service reads a key the function does not emit, which is a silently empty dashboard section rather than an error. |
| `test_the_dispatch_internals_stay_shut_and_the_resident_verb_opens` | The internals expose roster data and bypass request-level role checks, so only definer callers reach them -- `0037` §8's posture. The one function a person calls resolves the caller from `auth.uid()` and refuses a stranger itself, which is why `authenticated` is the right audience for it. |
| `test_it_verifies_itself_in_the_same_transaction` | `20260822090000` §2's shape: a file that claims to have added something fails rather than reporting success. The redefinition probes matter most -- an older body winning is a failure with no symptom. |
| `test_every_sqlstate_it_raises_is_one_the_api_can_map` | A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a generic message -- the one failure mode a resident cannot act on, because the sentence the RPC wrote never reaches them. |


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


## `test_session_capabilities.py`
What `capabilities` on the session promises, and who it promises it to.

`GET /auth/session` returns a list of words the frontend renders navigation
from. It is the *only* thing that decides whether an admin is offered the
resident portal at all -- there is no second check in the browser -- which makes
a wrong entry here invisible in exactly the way a wrong `portal` value is:
nothing errors, somebody is simply shown a door.

**The rule under test.** An admin is also a resident when they actually live
here. There is one `community_memberships` row per person per community
(`0001_baseline.sql`:45), so admin-ness and resident-ness are not two rows and
not two roles; resident-ness is an active `unit_residencies` row and nothing
else (product ruling, 2026-08-20). `require_resident_capability`
(`app/api/deps.py`) asks that table per request. This is the same question asked
once, at sign-in, from a read the session already performs -- so the two cannot
disagree.

They did. `capabilities.append("resident")` fired on `role == "admin"` alone,
which meant a flat-less admin -- a managing-committee member who owns nothing in
the society, which is common -- was shown the resident portal and then refused by
the guard on the first thing they clicked in it. A 403 nobody can act on is worse
than an absent menu item, because it looks like a bug in the software rather than
a fact about the account.

*Total tests in this file: 5*

| Test Function | Description |
|---------------|-------------|
| `test_an_admin_who_lives_here_is_also_a_resident` | Both capabilities, and the residency is what earns the second one. |
| `test_an_admin_who_lives_nowhere_is_only_an_admin` | The defect this module exists for.  A committee member who owns no flat is an ordinary account, not an edge case. The session used to hand them the resident portal on the strength of their role, and `require_resident_capability` would then refuse every write inside it -- so the menu item was real and everything behind it was a 403. |
| `test_the_embedded_residency_needs_no_supplemental_query` | The membership projection embeds the authoritative residency relation. |
| `test_a_resident_is_not_given_a_second_copy_of_their_own_capability` | The grant is admin-only. A resident's capability is their role, and the predicate must not have turned into "anyone with a residency". |
| `test_a_manager_with_a_flat_is_still_only_a_manager` | The ruling is about admins specifically, and widening it here would be a product decision wearing the clothes of a consistency fix. A manager who lives in the society reaches the resident portal the same way anybody else does -- by holding a `resident` membership -- and that is not this row. |


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

*Total tests in this file: 8*

| Test Function | Description |
|---------------|-------------|
| `test_resident_admin_and_worker_are_their_own_portal` | No description provided. |
| `test_plain_guard_stays_at_the_gate` | No description provided. |
| `test_security_rank_seniority_opens_the_manager_portal[manager]` | The spelling real people have.  `gate_admin_community_for` (`0040:589`) admits a `security` membership whose active roster row ranks manager or supervisor, and `supervisor` is in that list deliberately -- a supervisor holds the manager's writes, so the guard portal would leave them permissions with no screen. |
| `test_security_rank_seniority_opens_the_manager_portal[supervisor]` | The spelling real people have.  `gate_admin_community_for` (`0040:589`) admits a `security` membership whose active roster row ranks manager or supervisor, and `supervisor` is in that list deliberately -- a supervisor holds the manager's writes, so the guard portal would leave them permissions with no screen. |
| `test_manager_of_a_security_department_still_resolves` | Unreachable today, and kept: `manager` is a real `membership_role`. |
| `test_manager_of_a_service_department_is_not_a_gate_manager` | The `departments.kind` question is the reason that branch exists. |
| `test_manager_without_a_department_reads_nothing` | No description provided. |
| `test_embedded_rank_and_department_kind_need_no_portal_query` | No description provided. |


## `test_session_restoration.py`
Regression checks for the bounded, uncached session restoration path.

*Total tests in this file: 3*

| Test Function | Description |
|---------------|-------------|
| `test_established_member_session_uses_two_database_reads` | No description provided. |
| `test_request_dependencies_decode_and_build_the_user_client_once` | No description provided. |
| `test_only_a_present_refresh_cookie_marks_a_missing_access_as_expired` | No description provided. |


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


## `test_staff_assignment_employment_type_migration.py`
Regression contract for the service-hiring employment type.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_hiring_employment_type_remains_valid_for_the_hiring_rpc` | No description provided. |


## `test_supervisor_actions_migration.py`
`20260822170000_supervisor_actions.sql` -- what a static reader can prove
about a file nobody in this repository runs.

Amendment 2 of the supervisor dashboard: the buttons on the cards. It adds a
`complaint` chat thread, four complaint verbs, a hand-operated force-assign, a
re-bucketed snapshot, and **one** new `complaint_events` word.

The properties worth asserting without a database are these.

**Is the new event word the only one, and is the constraint's old vocabulary
intact?** The 2026-08-22 lesson (runbook 19) cost a whole extra migration:
`complaint_events_type_check` enumerates its words, so a word is a migration.
Recreating an enumerating constraint risks *losing* one, and a lost word poisons
every later insert of that type. So the list is not reviewed here -- it is
**derived** from `20260822150000`'s own text plus exactly `priority_changed`,
and compared. The same derivation is applied to `dm_threads_kind_check` against
`0046`.

**Is the copy of `post_dm_message` additive?** It is `0046`'s, redeclared whole
under the house convention to admit a department to its own complaint thread.
Every non-blank line of the owning file's version has to still be present
verbatim -- the 1--4000 check, the `HB404` that hides other people's threads, the
`HB409` lock and the notification are each things that can vanish without
anything erroring.

**Does `supervisor_resolve_complaint` avoid saying the same thing twice?**
`complaints_on_resolved` (`20260813104000`) already writes the `status_changed`
event, notifies the raiser and arms both auto-close timers when the status moves.
So this file must *not* -- and must fail its own apply if that trigger is
missing, because a Resolve that tells the resident nothing is the failure with no
symptom.

**Is the dead column still dead?** Ruling 1 of 2026-08-21. Resolve, priority and
notes are all triage; nothing here writes `assigned_to_membership_id` or
`assignee_label`.

**Is anything destructive beyond what it must be?** The four `drop`s this file is
allowed are named one by one, and everything else is forbidden.

*Total tests in this file: 42*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_the_snapshot_query_parses_on_its_own` | A syntax error in the query that fills the entire dashboard would sail past the whole-file parse and surface in the SQL editor, on a live database, in front of the owner. |
| `test_it_sorts_after_every_file_whose_work_it_builds_on` | Filename order is apply order.  `20260822150000` is the tightest: this file recreates the same constraint, and applying that one afterwards would silently drop `priority_changed` back out of the vocabulary. `0046` matters because the `complaint` kind is an extension of a CHECK that file creates, and `20260822120000` because the snapshot replaced here is the one it declared. |
| `test_it_is_the_last_word_on_both_functions_it_replaces` | Not "it is last in the directory" -- that property has expired five times in this directory already. The property is being last *among the files that declare this function*, which is what decides which body the database holds. |
| `test_it_redeclares_nothing_else_the_sibling_files_pin` | One function is copied forward and no others.  Each name below is one a sibling static-check file guards and one this file plausibly could have touched: the engine's own force-assign it is modelled on, the offer path it must leave byte-for-byte alone, the thread openers beside its own, the auto-close trigger it depends on, and the two functions phase one copied forward. Copying any of them forward to gain nothing would put this file in the way of the next person who needs to change one. |
| `test_it_never_writes_the_dead_complaint_column` | Ruling 1 of 2026-08-21, restated for amendment 2. Resolve, priority and notes are triage; who is going is a work-order assignment, and the whole design depends on not answering the second question by accident. |
| `test_the_new_event_list_is_the_old_list_plus_exactly_priority_changed` | Held by derivation rather than review.  Every word `20260822150000` allowed, plus the one word amendment 2 adds, and nothing else. A word dropped here would make the guard block refuse the apply (good) or, were the guard wrong, poison every later insert of that type (bad). |
| `test_the_file_writes_no_event_word_the_constraint_does_not_allow` | The 23514 of 2026-08-22, asked of this file before it is applied rather than after. Every literal this file inserts as an `event_type` must be in the list it recreates. |
| `test_the_thread_kind_list_is_the_old_list_plus_exactly_complaint` | The same derivation for `dm_threads_kind_check`, whose two words are `0046`'s. Losing `work_order` here would make every job chat unwritable. |
| `test_both_constraint_swaps_are_guarded_before_the_drop` | `20260822150000`'s shape, twice.  The guard runs before the DROP, so its exception leaves the old constraint standing untouched. Without it, a row outside the new list would fail the ADD with the old constraint already gone -- a table with no check on it at all. |
| `test_the_verification_proves_the_new_word_specifically` | A bare existence check would pass against the very constraint this file replaces. |
| `test_the_complaint_thread_is_one_row_per_complaint_and_cascades` | `on delete cascade` is forced rather than chosen: the subject CHECK makes `kind = 'complaint'` and a non-null `complaint_id` the same fact, so `set null` would raise 23514 and refuse to delete the complaint at all. |
| `test_only_the_thread_opener_writes_the_complaint_id` | One writer, asserted as a count. A second one -- a backfill, a trigger -- would attach a conversation to a complaint nobody opened it about. |
| `test_the_thread_seeds_the_frozen_sentence` | Approved copy, and the title is interpolated rather than described. |
| `test_the_opener_returns_the_existing_thread_before_it_resolves_a_pair` | "A later supervisor joins the existing thread rather than forking a second one" is this ordering and nothing else: the lookup happens before the pair is computed, so the second supervisor gets the first one's thread with their own right to write it coming from the policy rather than from the row. |
| `test_the_lock_mirrors_the_job_thread_and_reopens_what_a_job_cannot` | `closed \| cancelled` shuts the channel and says so in it; anything else opens it again. The `else` arm is the one difference from `0046`'s trigger, and it exists because a complaint can be reopened and a job cannot. |
| `test_reading_and_writing_a_complaint_thread_ask_the_same_question` | One rule, three places, and they cannot drift because all three call it.  A read policy that admitted the department while `post_dm_message` did not would be a chat a supervisor can open, watch, and never answer in. |
| `test_the_post_message_copy_is_purely_additive` | The house convention, checked rather than promised.  Every non-blank line of `0046`'s `post_dm_message` has to still be present. The length check, the `HB404` that hides other people's threads, the `HB409` lock, the `last_message_at` bump and the counterpart notification are all lines that can vanish without anything erroring -- and the lock is the whole of amendment 2's write-locking requirement. |
| `test_the_post_message_copy_keeps_its_signature_and_return_type` | `create or replace` refuses a changed return type and would fail on the hosted database; a new defaulted parameter would create an overload rather than replace anything, which fails silently and is worse. |
| `test_resolve_refuses_a_running_job_and_a_settled_complaint` | The refusal the button exists to produce well. Somebody is inside a resident's flat: the honest answers are to let them finish or to cancel the visit, and both are somebody's deliberate act. |
| `test_resolve_cancels_every_other_live_job_and_tells_its_worker_why` | Ruling A2's other half, with the frozen reason. A worker holding an offer must not find out from an empty queue, and an assignment is withdrawn rather than deleted -- one holder at a time, and the history survives. |
| `test_resolve_leaves_the_status_event_and_the_notification_to_the_trigger` | `complaints_on_resolved` (`20260813104000`) writes the `status_changed` row, notifies the raiser `complaint.resolved` and arms both auto-close timers when the status moves. This function moves the status, so all four happen in the same transaction. Writing them here as well would put two "Status changed to Resolved" lines on one timeline and buzz one phone twice. |
| `test_the_file_refuses_to_apply_without_the_auto_close_trigger` | Because the paragraph above is a dependency and not a comment. A hosted database missing `complaints_on_resolved` would give this feature a Resolve button that tells the resident nothing, with nothing anywhere erroring. |
| `test_priority_is_one_way_and_stops_at_high` | A supervisor who could lower a priority could quietly un-escalate something somebody else escalated -- a different decision, worth a different verb and a different audit line. |
| `test_priority_moves_the_live_jobs_with_the_complaint` | A job's urgency *is* its complaint's urgency -- `create_work_order` never took a priority argument for exactly that reason. A live job left at the old value is a dispatcher acting on the answer before the escalation. |
| `test_priority_writes_the_event_in_storage_vocabulary_and_notifies_nobody` | The payload carries `medium`/`high`; the sentence the resident reads says *Medium*/*High*, and `app/domain/vocabularies.py` is the seam. A `case` in SQL would be a second copy of that table in a language nobody would look in. |
| `test_a_note_is_flagged_internal_and_bounded` | Ruling A5: the flag is on the payload rather than in a new event word -- which would have cost the constraint rebuild a second time -- so the admin's resident-visible notes, which carry no flag, are untouched. |
| `test_every_complaint_verb_asks_the_same_guard_the_snapshot_asks` | One predicate, five callers. A verb that asked a different question from the dashboard it is pressed on would put a button on a card that refuses it. |
| `test_an_unrouted_complaint_is_a_conflict_and_not_a_refusal` | Phase one's call, ratified by the orchestrator and applied to all four verbs: there is no department to supervise, so `HB403` would tell a supervisor they lack a permission when what is missing is the routing. |
| `test_force_assign_is_the_engine_s_mechanics_with_a_guard` | Modelled on `dispatch_force_assign` and deliberately not a second mechanism: the same `is_forced` accepted row, the same two timeline events, the same notifications. What it adds is the guard the dispatcher does not need -- this caller is a person. |
| `test_force_assign_withdraws_the_previous_holder_and_refuses_a_closed_job` | The assign idiom: one holder at a time, withdrawn rather than deleted, and a terminal job refused. Forcing overrides the worker's consent, not the state machine. |
| `test_force_assign_takes_the_frozen_two_arguments_and_defaults_the_rest` | The spec froze `force_assign_work_order(work_order_id, staff_assignment_id)`. The two slot parameters default to null, so that call is exactly this function -- and a supervisor who picked the person and the hour in one gesture does not need a second round trip to set the time. |
| `test_the_five_buckets_are_defined_here_and_only_here` | The frozen contract says the frontend renders the arrays as-is, which means these five predicates are the definitions and not a copy of them.  *Committed* replaces phase one's *engaged* and the difference is one word: an `offered` assignment no longer counts, because a job nobody has accepted is an open request rather than assigned work. |
| `test_the_two_complaint_sections_exclude_any_live_work_order` | "Furthest stage wins": a complaint with a job appears once, as that job, in whichever of sections 3-5 it has reached. Phase one excluded only *engaged* work, which put an unaccepted job's complaint in section 2 and its work order nowhere. |
| `test_the_two_names_are_two_facts` | `assigneeName` is the person who accepted; `offeredToName` is the person who has been asked. One field carrying both would make a section-3 card read "Ravi is coming" about a job Ravi has not answered. |
| `test_the_snapshot_is_replaced_wholesale_and_still_writes_nothing` | Dropped and recreated rather than replaced, because it is a different answer to the same question and the old one should not be reachable by a caller who missed the change. It remains a read: `stable`, and no write verb anywhere in it. |
| `test_every_section_is_newest_first_and_translates_no_vocabulary` | One ordering, five times. The urgent stack is the frontend's own pinning and is deliberately not sorted for here. |
| `test_the_python_wire_model_agrees_with_the_rpc` | The half-landed change this catches: the SQL ships and the service reads a key the function does not emit, which is a silently empty dashboard section rather than an error. |
| `test_the_only_ddl_is_what_this_file_declares_it_makes` | Four `drop`s, each named, and nothing else destructive.  The snapshot is dropped because it is being replaced by a different answer; the two policies and the trigger are dropped because `create policy` and `create trigger` have no `or replace`. Everything else -- a table, a column, a view, an index, a row -- is out of bounds. |
| `test_every_sqlstate_it_raises_is_one_the_api_can_map` | A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a generic message -- the one failure mode a supervisor cannot act on, because the sentence the RPC wrote never reaches them. |
| `test_it_verifies_itself_in_the_same_transaction` | `20260822090000` 2's shape: a file that claims to have added something fails rather than reporting success. The two `prosrc` probes are the ones that matter most -- a `create or replace` that lost the department clause from `post_dm_message`, or an older snapshot winning, are both failures with no symptom. |
| `test_every_new_function_is_granted_to_somebody` | A definer function nobody may execute is a feature that fails with 42501 at the first press. The trigger function is the deliberate exception: it runs as the trigger's owner and has no business being callable. |


## `test_supervisor_triage_migration.py`
`20260822120000_supervisor_triage.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It adds the four facts the supervisor dashboard needs and the model
could not say: that a supervisor has *picked a complaint up*, when a worker
actually *started*, and that a job arrived by somebody else's removal rather than
by the reader's own hand.

The properties worth asserting without a database are these.

**Does it sort last, and does it stay out of the other files' way?** Five sibling
static-check files pin earlier migrations by name. This one redeclares two
functions on purpose and must redeclare nothing else.

**Are the two copies additive?** `start_work_order` (`0039`) and
`restamp_department_supervision` (`20260821200000`) are reproduced whole under
the house convention (`20260812113000` 1) to gain one stamp each. A copy that
quietly dropped the resident notification, an `HB404`, the successor lookup or
the `get diagnostics` would not error -- it would delete behaviour. So every
non-blank line of the owning file's version is required to still be present,
verbatim, which is the check that catches a copy made by retyping.

**Do the two new columns have exactly one writer each?** `taken_up_at` is
`take_up_complaint`'s and `supervision_inherited_at` is
`restamp_department_supervision`'s. A second writer for either is a dashboard
section that fills up for reasons nobody chose.

**Is the dead column still dead?** Ruling 1 of 2026-08-21: nothing new writes
`complaints.assigned_to_membership_id` or `assignee_label`. Take-up is triage
ownership and is exactly the change most likely to be mistaken for dispatch, so
the absence is asserted rather than argued.

**Is anything destructive?** Nothing here may drop a column, a function, a table
or a policy, and nothing may delete a row. The only DDL shapes are `add column if
not exists` and `create index if not exists`.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it -- the whole file, and then the snapshot query on its own, because a
function body is an opaque string to the outer parse -- is as close as this suite
gets. The rest is in `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 18.

*Total tests in this file: 29*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_the_snapshot_query_parses_on_its_own` | The check the whole-file parse cannot make.  Everything interesting in this file is inside a `$$ ... $$` body, which the outer parse reads as one opaque string -- so a syntax error in the query that fills the entire dashboard would sail past `test_the_migration_parses_as_postgresql` and surface in the SQL editor, on a live database, in front of the owner. |
| `test_it_sorts_after_every_file_whose_work_it_builds_on` | Filename order is apply order.  `20260821200000` is the tightest: this file copies its `restamp_department_supervision` forward, and sorting before it would mean the version *without* the stamp is applied second and wins -- silently, because both files declare the same name. `20260822090000` matters for a different reason: until that file is applied nothing can insert a `work_orders` row at all, so a column added here would be a column on a table nobody can write. |
| `test_it_is_the_last_word_on_both_functions_it_copies` | Not "it is last in the directory" -- that property has expired four times in this directory already. The property is being last *among the files that declare this function*, which is what decides which body the database ends up holding. |
| `test_it_redeclares_nothing_else_the_sibling_files_pin` | Two functions are copied forward and no others.  Each name below is one a sibling static-check file guards, and each is one this file plausibly *could* have touched: the trigger that calls the re-stamp, the successor rule behind it, the status projection that gains a second writer for `acknowledged`, and the department queue whose read the snapshot generalises. Copying any of them forward to gain nothing would put this file in the way of the next person who needs to change one. |
| `test_it_never_writes_the_dead_complaint_column` | Ruling 1 of 2026-08-21, restated by ruling 1 of 2026-08-22 because take-up is the change most easily mistaken for dispatch.  `complaints.assigned_to_membership_id` has one writer (`update_complaint`, `0031`) and no reader anywhere. Take-up records who is *looking at* a complaint; who is going is a work-order assignment, and the whole design depends on not answering the second question by accident. |
| `test_take_up_is_the_only_writer_of_the_take_up_columns` | One writer, asserted as a count rather than promised in prose.  A second writer -- a backfill, a trigger, a convenience `update` in the snapshot -- would fill the dashboard's second section for reasons nobody chose, and there is no error anywhere to notice it by. |
| `test_take_up_moves_the_status_only_from_open` | Ruling 2, and the half of it that is not the headline.  `acknowledged` gains a second writer deliberately. What it must not gain is a path that walks a complaint *backwards*: one a worker has already started is `in_progress`, and a triage button is not a reason to un-start it. |
| `test_take_up_writes_the_timeline_and_notifies_nobody` | A passive field change under ARCHITECTURE.md's rule.  The resident learns the same fact from the status their screen re-snapshots within a beat, so a notification would be a second telling of one thing. The timeline entry is not the same category: it is the record, and `0020`'s reader renders it. |
| `test_take_up_refuses_three_ways_and_is_idempotent_for_its_owner` | 404 unknown, 403 not yours, 409 somebody else's -- and a second press by the same person is a no-op rather than the 409 a naive implementation gives it. A double-clicked button is not an error worth a message. |
| `test_take_up_refuses_an_unrouted_complaint_as_a_conflict_not_a_refusal` | There is no department to supervise, so `HB403` would tell a supervisor they lack a permission when what is missing is the routing. |
| `test_the_start_copy_is_purely_additive` | The house convention, checked rather than promised.  Every non-blank line of `0039`'s `start_work_order` has to still be present. The resident notification, both `HB404`s, the `HB409`, the already-started early return and the `job_started` event are all lines that can vanish without anything erroring -- and the last of them is what the resident's timeline is built from.  This is also why the added assignment is written leading-comma style: the line `set status = 'in_progress', updated_at = now()` survives verbatim, so the copy is *provably* additive rather than additive-looking. |
| `test_the_restamp_copy_is_purely_additive` | The same check for `20260821200000`'s `restamp_department_supervision`.  The successor lookup, the "nothing to move" pre-check, the department scope on both the check and the update, and `get diagnostics` are each load-bearing: losing the scope would hand a membership's work in *every* department to whichever one lost them first, and losing the diagnostics would make the last-supervisor notice claim zero jobs moved. |
| `test_neither_copy_changes_its_signature_or_return_type` | `create or replace` refuses a changed return type and would fail on the hosted database; a new defaulted parameter would create an overload rather than replace anything, which fails silently and is worse. |
| `test_each_stamp_has_exactly_one_writer` | `started_at` is the worker's Start and `supervision_inherited_at` is the re-stamp, and neither is written anywhere else in this file.  A stamp with two writers is a dashboard badge that appears for two different reasons, one of which nobody documented. |
| `test_the_start_stamp_cannot_be_reset` | `coalesce(started_at, now())`, not `now()`.  The already-`in_progress` early return means a second press cannot reach the statement today. It is written defensively anyway because the dashboard's elapsed time is measured from this column, and a future writer that reaches `in_progress` some other way should not be able to restart the clock. |
| `test_the_inherited_stamp_marks_only_what_the_restamp_moves` | Same row, same statement, same scope. Marking rows the re-stamp did not move would badge work that arrived by somebody's own hand as inherited. |
| `test_the_snapshot_asks_the_same_guard_the_department_queue_asks` | `can_supervise_department`, and a refusal rather than an empty snapshot.  An empty dashboard and a refused one look identical on a screen, and the difference is the whole content of the answer. The predicate is the one `department_complaints` (`20260813103000`) and `create_work_order` (`0036`) already ask, so the dashboard and the verbs on it agree about who may act. |
| `test_the_snapshot_writes_nothing` | It is a read and it decides nothing -- the claim `COMPLAINT_ENGINE_HANDOFF.md` 18 makes on this engine's behalf. `stable` is the declaration of that, and the absence of every write verb is the proof. |
| `test_the_four_buckets_are_defined_here_and_only_here` | The frozen contract says the frontend renders the arrays as-is.  Which means these four predicates are the definitions, not a copy of them. Each is asserted by the shape that makes it wrong if it drifts: `new` is untouched work, `taken_up` is stamped work nobody is engaged on, `assigned_pending` is engaged work that has not started, `in_progress` is what the worker started. |
| `test_every_section_is_newest_first` | One ordering, four times. The urgent stack is the frontend's own pinning and is deliberately not sorted for here -- a server that pre-pinned would be deciding a layout. |
| `test_the_snapshot_never_translates_a_vocabulary` | `app/domain/vocabularies.py` is the one place this codebase maps a stored word to a rendered one. A `case` in SQL turning `high` into `High` would be a second copy of that table, free to disagree with it, in a language where nobody would think to look for it. |
| `test_the_reroute_marker_is_derived_from_the_timeline_and_not_a_column` | `reroutedAt` is the newest `department_assigned` event naming *this* department as the destination.  `raise_complaint` writes `raised` rather than `department_assigned` (`20260812090300` 3), so automatic routing at raise time is correctly not a reroute -- only an admin allotting, a manager moving, or an accepted transfer request is. A column would also have been wrong: a complaint can arrive here more than once, and the events already record every arrival. |
| `test_the_snapshot_reads_the_two_new_stamps` | The columns exist for these two sections and would otherwise be write-only.  `startedAt` is what makes "being worked right now" show for how long, and `inheritedAt` is the badge ruling 3 partially reversed `16`'s "no new column" to make possible. |
| `test_the_four_columns_are_added_additively_and_nullable` | `add column if not exists`, which is what has always applied cleanly around the hosted tables' legacy columns (`20260820120000`, `20260822090000`).  Nullable with no default, deliberately: `taken_up_at is null` **is** the answer to "is this untouched", and a default would make every row that predates this file claim a moment nobody lived through. |
| `test_nothing_is_destructive` | This file adds. It may not remove anything, and it has no view or trigger to drop and recreate -- so unlike its siblings, the count of `drop` statements it is allowed is zero. |
| `test_every_sqlstate_it_raises_is_one_the_api_can_map` | A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a generic message -- which is the one failure mode a supervisor cannot act on, because the sentence the RPC wrote never reaches them. |
| `test_it_verifies_itself_in_the_same_transaction` | `20260822090000` 2's shape: a file that claims to have added something fails rather than reporting success.  The two `prosrc` probes are the ones that matter most, because a `create or replace` losing its stamp is the failure with no symptom -- the dashboard section simply stays empty and nothing anywhere errors. |
| `test_the_python_wire_model_agrees_with_the_rpc` | The half-landed change this catches: the SQL ships and the service reads a key the function does not emit, which is a silently empty dashboard section rather than an error. |


## `test_taken_up_event_word_migration.py`
`20260822150000_taken_up_event_word.sql` -- what a static reader can prove.

`take_up_complaint` (20260822120000) writes `event_type = 'taken_up'`;
`complaint_events_type_check` (20260813105000) enumerates the allowed words
and did not know it. The first live Take-up press answered 23514 on
2026-08-22. The cure recreates the constraint with exactly one new word.

The hazard of recreating an enumerating constraint is losing a word: any
already-allowed type missing from the new list would make the guard block
refuse the apply (good) or, were the guard wrong, poison every later insert
of that type (bad). So the word list is not reviewed here -- it is **derived**
from the creating migration's own text and compared exactly.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_the_creator_and_the_breaker` | No description provided. |
| `test_the_new_list_is_the_old_list_plus_exactly_taken_up` | Held by derivation rather than review: every word the creator allowed, plus the one word the breaker writes, and nothing else. |
| `test_the_breaker_writes_no_other_new_word` | If 20260822120000 inserted a second unknown word, this cure would fix one 23514 and leave its sibling live behind a passing apply. |
| `test_the_only_ddl_is_the_constraint_swap` | No description provided. |
| `test_the_guard_refuses_and_the_verification_fails` | The guard runs before the DROP, so its exception leaves the old constraint standing. The verification may only EXCEPTION, and must prove the new word specifically -- a bare existence check would pass against the very constraint this file replaces. |


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


## `test_visitor_requests_sse_migration.py`
`20260823160000_visitor_requests_sse.sql` -- `0007`'s own trigger for
`visitor_requests`, arriving twenty-five files late.

`0007_dashboard_realtime_outbox.sql` loops twelve table names and builds
`dashboard_sse_%I` on each one that exists. `visitor_requests` is in that array,
so a fresh database has had the trigger since `0007`. Hosted has not: when
`0007` was applied there the baseline table did not yet exist -- `0032` created
it -- the `to_regclass` guard skipped it, and nothing revisited the question.
The owner's probe of 2026-08-23 found `visitor_requests` carrying no trigger at
all while holding the only three real visitor requests in the project (runbook
§22 probes (g) and (h), §26).

So the file must not invent a trigger; it must reproduce the one `0007` would
have made. That is the derivation this suite is built on: the name, the events,
the row/statement level and the function are all read out of `0007`'s own loop
template and compared against the statement in this file. If `0007` is ever
edited, these tests fail rather than letting the two definitions drift.

The other end is pinned too: the table this trigger fires on is read out of
`dashboard_repository.list_visitors`, because a realtime signal on a table the
dashboard does not read would be a refresh that shows nothing new.

**Not verifiable statically:** whether hosted's `emit_dashboard_sse_event` is
`0007`'s. It is a `create or replace` in `0007` and no later file touches it,
which is checked below; the rest is the apply's business.

*Total tests in this file: 9*

| Test Function | Description |
|---------------|-------------|
| `test_the_migration_parses_as_postgresql` | No description provided. |
| `test_it_sorts_after_the_file_it_had_to_follow` | Forward-only. A version below the latest on a shared branch is invisible to a fresh replay that has already passed it. |
| `test_it_sorts_after_the_outbox_and_after_the_table_it_triggers` | The trigger function comes from `0007` and the table from `0032`; a fresh replay must have both before this file runs. |
| `test_the_trigger_is_the_one_0007_would_have_built` | Name and definition both derived from `0007`'s loop template, so the trigger a fresh database gets from `0007` and the trigger hosted gets from here are the same trigger -- including the `delete` arm, which the outbox fires on and a hand-written pair might have left out. |
| `test_the_table_is_one_0007_already_names` | This is `0007` finishing its own job, not a thirteenth table being added to the outbox by a side door. `visitor_requests` has been in that array since the file was written; it was skipped by the `to_regclass` guard on a database where the table did not exist yet. |
| `test_the_table_is_the_one_the_dashboard_reads` | The realtime half and the read half of the split-brain fix must point at the same table, or the refresh arrives about rows nobody projects. |
| `test_every_definition_of_the_trigger_function_is_already_applied` | `emit_dashboard_sse_event` is written by `0007` and rewritten once, by `0028_event_audience.sql`, which retargets `dashboard.refresh` at the `{admin, manager}` audience. Both sort before this file, which is what makes "the same trigger a fresh database has" a settled statement: whichever database this runs on, the function the trigger names is already in its final form. A future rewrite sorting *after* this file would be fine for the trigger and is still worth being told about -- the emitted audience is the thing that decides whether an admin's dashboard hears about a visitor at all. |
| `test_it_drops_nothing_and_is_idempotent` | `create or replace trigger` rather than a drop-and-create pair: there is no window in which the table has no trigger, and a second run replaces the file's own work rather than removing somebody else's. |
| `test_it_verifies_the_trigger_it_claims_to_have_made` | A named check rather than a bare existence one: the table already had no trigger, so 'some trigger is present' would pass against nothing useful. |


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


## `test_worker_repository.py`
No description provided.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_worker_job_read_retries_without_the_v2_column_on_legacy_view` | No description provided. |


