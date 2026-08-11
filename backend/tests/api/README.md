# API Tests Documentation

> **Note:** This file is auto-generated dynamically by a pytest hook in `conftest.py`. It extracts descriptions directly from the python code docstrings during test collection.

## `test_access_requests.py`
Resident access-request and administrator-decision API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_005_resident_creates_access_request` | No description provided. |
| `test_api_006_admin_approves_access_request` | No description provided. |


## `test_amenities.py`
Amenity-booking API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_007_partial_booking_cancellation_returns_cancelled_day_count` | No description provided. |
| `test_api_008_booking_cancellation_rejects_empty_date_selection` | No description provided. |


## `test_auth.py`
Authentication API cases.

*Total tests in this file: 5*

| Test Function | Description |
|---------------|-------------|
| `test_api_003_auth_methods_returns_configured_methods` | No description provided. |
| `test_api_004_refresh_timeout_returns_service_unavailable` | No description provided. |
| `test_api_005_sign_in_with_an_unconfirmed_email_is_refused` | No session cookie may be set for an address nobody has proven they own. |
| `test_api_006_resend_reaches_the_provider_and_reveals_nothing` | The route used to return its reassurance without sending anything. |
| `test_api_007_email_confirmation_establishes_browser_session` | No description provided. |


## `test_complaints.py`
Complaint workflow API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_009_admin_updates_complaint_progress` | No description provided. |
| `test_api_010_resident_comments_on_complaint` | No description provided. |


## `test_contract_consistency.py`
Check API documentation and runtime responses for contract consistency.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_api_016_openapi_422_schema_matches_runtime` | No description provided. |


## `test_events.py`
`GET /events` -- the canonical live-update stream, and its deprecated alias.

The fan-out and the audience filter are tested against the real asyncio
machinery in ``tests/test_realtime.py``. What is left here is the HTTP surface:
the guard, the headers a stream has to get right, and the fact that the two
paths are one handler rather than two implementations that can drift.

The service layer is replaced with a generator that ends, because the real one
does not: a live stream yields a heartbeat every 20 seconds and never stops, so
a test that read it would block until the timeout rather than pass.

*Total tests in this file: 23*

| Test Function | Description |
|---------------|-------------|
| `test_the_stream_requires_a_session[/api/v1/events]` | No description provided. |
| `test_the_stream_requires_a_session[/api/v1/dashboard/events]` | No description provided. |
| `test_a_resident_may_open_the_stream[/api/v1/events]` | The guard is membership, not role -- it always was. What changed in `0028` is that the rows now carry an audience, so letting a resident in is no longer the same thing as showing them their neighbours' join requests. |
| `test_a_resident_may_open_the_stream[/api/v1/dashboard/events]` | The guard is membership, not role -- it always was. What changed in `0028` is that the rows now carry an audience, so letting a resident in is no longer the same thing as showing them their neighbours' join requests. |
| `test_the_stream_is_never_cached_or_buffered[/api/v1/events]` | Both are load-bearing. A cached stream is served once and never updates; an nginx-buffered one shows the browser nothing until the buffer fills. |
| `test_the_stream_is_never_cached_or_buffered[/api/v1/dashboard/events]` | Both are load-bearing. A cached stream is served once and never updates; an nginx-buffered one shows the browser nothing until the buffer fills. |
| `test_the_identity_comes_from_the_resolved_membership[/api/v1/events]` | All three values the audience filter runs on are read off the membership the dependency resolved out of Postgres. Nothing here is client-supplied. |
| `test_the_identity_comes_from_the_resolved_membership[/api/v1/dashboard/events]` | All three values the audience filter runs on are read off the membership the dependency resolved out of Postgres. Nothing here is client-supplied. |
| `test_last_event_id_is_forwarded_as_a_cursor[/api/v1/events]` | No description provided. |
| `test_last_event_id_is_forwarded_as_a_cursor[/api/v1/dashboard/events]` | No description provided. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[-/api/v1/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[-/api/v1/dashboard/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[  -/api/v1/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[  -/api/v1/dashboard/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[not-a-number-/api/v1/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[not-a-number-/api/v1/dashboard/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[-7-/api/v1/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[-7-/api/v1/dashboard/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[9e9e9-/api/v1/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422[9e9e9-/api/v1/dashboard/events]` | The header is written by the browser's own `EventSource`, not by application code. Refusing the reconnect would leave a client with no way back other than to stop sending a header it is required to send. |
| `test_the_cursor_can_only_seek_never_widen` | A negative or absent value clamps to zero; a valid one is only ever a position in a stream the caller is already authorized for. |
| `test_the_old_path_is_marked_deprecated_and_the_new_one_is_not` | A client generated from the spec should be steered to `/events`, and the admin frontend that is already on the old path should keep working. |
| `test_both_paths_declare_the_stream_media_type` | FastAPI defaults an un-inferable return type to `application/json`, and a client generated from that would try to JSON-decode a live stream. |


## `test_money.py`
Invoice and payment validation API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_013_invoice_rejects_empty_line_items` | No description provided. |
| `test_api_014_payment_rejects_zero_amount` | No description provided. |


## `test_notices.py`
Notice publication API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_011_admin_publishes_notice` | No description provided. |
| `test_api_012_notice_rejects_empty_title` | No description provided. |


## `test_notifications.py`
The notification feed and Web Push registration.

Three things are tested and they are worth keeping apart.

The **HTTP surface** -- who may call, which membership the query is scoped to,
what the response may not contain. The repository is replaced, and the
substitute records its arguments, which is how the recipient assertions are made.

The **projection** -- what a stored `payload` becomes. Those go through the
service directly: the interesting cases are payload shapes, and routing one
through a request would only add noise between the input and the assertion.

The **push configuration gate** -- that an environment with no VAPID keypair
returns 503 on the two endpoints that need one, and nothing else changes. That
is the whole of §10.5's "fail closed, but do not fail loudly", and it is the part
most likely to be broken by someone tidying the settings class later.

*Total tests in this file: 36*

| Test Function | Description |
|---------------|-------------|
| `test_the_feed_requires_a_session` | No description provided. |
| `test_a_resident_reads_their_own_feed` | No description provided. |
| `test_an_admin_has_a_feed_too` | `complaint.raised` and `access_request.created` are addressed to admins. A feed that refused them would mean building a second one later. |
| `test_the_recipient_is_the_resolved_membership` | No description provided. |
| `test_a_query_parameter_cannot_choose_the_recipient` | There is no recipient parameter, so nothing reads one. The RLS policy on `notifications` would refuse anyway -- this asserts the layer above it. |
| `test_the_unread_filter_reaches_the_query` | No description provided. |
| `test_paging_is_translated_to_an_offset` | No description provided. |
| `test_invalid_paging_is_rejected_before_the_feed_is_queried[page=0]` | The page bounds protect an endpoint whose backing table grows forever.  Validation has to happen before either the page query or the badge-count query. Otherwise a malformed request can still spend database work even though its response is a 422. |
| `test_invalid_paging_is_rejected_before_the_feed_is_queried[pageSize=0]` | The page bounds protect an endpoint whose backing table grows forever.  Validation has to happen before either the page query or the badge-count query. Otherwise a malformed request can still spend database work even though its response is a 422. |
| `test_invalid_paging_is_rejected_before_the_feed_is_queried[pageSize=101]` | The page bounds protect an endpoint whose backing table grows forever.  Validation has to happen before either the page query or the badge-count query. Otherwise a malformed request can still spend database work even though its response is a 422. |
| `test_the_unread_count_is_the_whole_feed_not_the_page` | A badge counts the feed. If it counted the page it would change as the resident scrolled, which is the bug this separate query exists to avoid. |
| `test_an_empty_feed_is_a_page_not_a_404` | No description provided. |
| `test_the_feed_is_camel_case` | No description provided. |
| `test_the_raw_payload_never_reaches_the_client` | The response carries rendered strings, not the stored document. This is what makes §10.8's one hard rule enforceable: a writer that puts a secret in `payload` finds it stays in the database. |
| `test_marking_read_returns_the_remaining_unread_count` | No description provided. |
| `test_marking_someone_elses_notification_read_is_a_404` | The RPC returns false for a row that does not exist and for one that is not the caller's, and both become the same 404. Distinguishing them would let a caller enumerate ids. |
| `test_marking_read_requires_csrf` | No description provided. |
| `test_read_all_reports_what_moved_and_what_is_left` | `unread` is re-read rather than assumed to be zero: a notification can arrive between the update and the count. |
| `test_a_payload_title_and_body_are_used_as_written` | No description provided. |
| `test_a_missing_title_falls_back_to_one_derived_from_the_kind` | The writers arrive in later build steps. A kind whose author forgot a title should produce a dull row rather than a blank one -- an empty line in a feed reads as a bug in the app. |
| `test_an_unknown_kind_still_renders` | Hiding it would mean a notification the system decided to send and the resident never learns exists. |
| `test_render_copies_no_field_it_was_not_asked_for` | The enforcement point for "the visitor security code may never appear in a push body" (§10.8). It is not a check -- there is simply no code path that copies a fourth key. |
| `test_a_non_dict_payload_does_not_break_the_row` | `payload` is `jsonb` with no constraint, so a string or a list is representable even though nothing writes one. |
| `test_the_vapid_key_is_served_to_a_member` | No description provided. |
| `test_the_vapid_key_requires_a_session` | Public by construction, but an unauthenticated endpoint that names our push key is free reconnaissance for no benefit. |
| `test_the_private_key_is_never_served` | No description provided. |
| `test_subscribing_accepts_the_browsers_own_document` | `PushSubscription.toJSON()`, posted unchanged. A transcription step is somewhere to put `auth` into the `p256dh` field, and that failure looks like a push that silently never decrypts. |
| `test_a_subscription_is_bound_to_the_resolved_membership` | Nothing in the body says who this is for. If it did, one resident could subscribe a device to another's notifications. |
| `test_a_subscription_without_keys_is_rejected` | No description provided. |
| `test_a_subscription_with_an_empty_encryption_key_is_rejected_before_storage[keys0]` | An empty browser key would create a subscription that can never decrypt.  This is deliberately a request-boundary test: the repository is never called, so an invalid browser document cannot replace a known-good device registration at the idempotent endpoint. |
| `test_a_subscription_with_an_empty_encryption_key_is_rejected_before_storage[keys1]` | An empty browser key would create a subscription that can never decrypt.  This is deliberately a request-boundary test: the repository is never called, so an invalid browser document cannot replace a known-good device registration at the idempotent endpoint. |
| `test_unsubscribing_takes_the_endpoint_in_the_body` | Not a query string: a push endpoint is a device identifier, and a request whose purpose is to stop tracking a device should not write it into every access log on the way. A `POST` to a sub-path rather than a `DELETE`, because content on a `DELETE` has no defined semantics and may not survive the trip. |
| `test_the_vapid_key_is_a_503_when_push_is_not_configured` | No description provided. |
| `test_subscribing_is_a_503_when_push_is_not_configured` | A subscription created against no keypair is bound to nothing, and the resident would have spent a notification permission prompt on a channel that can never deliver. |
| `test_unsubscribing_works_without_a_keypair` | Turning notifications off must not depend on an operator not having lost a key. |
| `test_the_rest_of_the_api_is_unaffected_by_missing_push_configuration` | Push is an enhancement. An unconfigured environment must not be a broken environment -- the same shape as `0024` no-opping without `pg_cron`. |


## `test_onboarding.py`
Founder and invitation activation regressions.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_founder_creation_verifies_identity_then_calls_onboarding` | No description provided. |
| `test_founder_identity_failure_is_an_authentication_response` | No description provided. |
| `test_invitation_redemption_verifies_identity_before_redeeming` | No description provided. |
| `test_invitation_identity_failure_is_an_authentication_response` | No description provided. |


## `test_resident_amenities.py`
`GET /amenities/available` -- the resident amenity catalogue.

Two things are being tested and they are worth keeping apart.

The **HTTP surface**: who may call it, which community it reads, and the fact
that the response cannot carry an admin field. The repository is replaced so
nothing touches Supabase; the substitute records its arguments, which is how the
tenancy assertions are made -- checking that the community reaching the query is
the one the membership resolved, not something a caller supplied.

The **projection**: what a database row becomes. Those tests go through the
service directly rather than over HTTP, because the interesting cases are row
shapes (a null capacity, a zero maximum, a closure written as an empty object)
and routing one through a request would only add noise between the input and the
assertion.

*Total tests in this file: 31*

| Test Function | Description |
|---------------|-------------|
| `test_the_catalogue_requires_a_session` | No description provided. |
| `test_a_resident_may_read_the_catalogue` | The whole point of the endpoint. Before it, the only path to an amenity id was `GET /dashboard/snapshot`, which a resident is refused. |
| `test_an_admin_may_read_the_catalogue_too` | The guard is any active membership, not `resident`. Nothing in this response is per-resident, so there is nothing role-shaped to scope. |
| `test_the_community_comes_from_the_membership` | Tenancy is the community `get_active_membership` resolved out of Postgres. There is no community parameter on this route, so this is the only value that can reach the query. |
| `test_an_unknown_query_parameter_cannot_widen_the_read` | FastAPI ignores undeclared query parameters rather than rejecting them, so the guarantee has to be that nothing reads them -- not that nobody sends them. |
| `test_the_response_carries_no_admin_figures` | `pendingRequests` and `outstandingDues` are on the admin card and are the reason this projection is a separate model. If either ever appears here, the endpoint has been pointed at `amenity_overview`. |
| `test_the_response_is_camel_case` | No description provided. |
| `test_an_empty_catalogue_is_a_page_not_a_404` | No description provided. |
| `test_the_page_reports_the_whole_catalogue` | Unpaged on purpose -- `hasMore` false means the client has everything. |
| `test_a_truncated_catalogue_says_so_rather_than_claiming_completeness` | The read is bounded. If the bound ever cuts the catalogue short, the envelope has to say so: `hasMore: false` over a truncated list is the endpoint claiming completeness it did not check, and a client has no way to detect it. |
| `test_a_closed_amenity_is_not_reported_as_a_further_page` | A row dropped by the closure test was returned by the query, not withheld by the bound. Counting it as more to fetch would send a client after a row it is never meant to see. |
| `test_times_are_truncated_to_the_minute` | Postgres sends `06:00:00`; an `<input type="time">` needs `06:00`. |
| `test_a_missing_opening_hour_reads_as_midnight_not_null` | Weaker than it looks, and deliberately: the booking RPC refuses a slot outside opening hours, not this string. What it buys is a client that does not have to special-case absence when comparing times. |
| `test_amounts_survive_arriving_as_strings` | PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as a string on some versions. Parsed once, at the boundary. |
| `test_an_unparseable_amount_reads_as_zero_rather_than_failing` | No description provided. |
| `test_closed_days_become_weekday_names` | No description provided. |
| `test_an_out_of_range_closed_day_is_dropped_not_rendered` | No description provided. |
| `test_booking_mode_is_translated_to_the_wire_vocabulary` | No description provided. |
| `test_a_zero_limit_reads_as_no_limit` | A maximum duration of zero would be read by a booking form as "no booking is long enough", which is never what the column meant. |
| `test_a_missing_slot_duration_falls_back_to_an_hour` | The one limit that cannot be null on the wire: a client divides the day by it, and dividing by nothing is worse than dividing by the schema default. |
| `test_the_currency_is_upper_cased` | No description provided. |
| `test_null_text_reads_as_empty_string_not_null` | No description provided. |
| `test_a_missing_category_falls_back_to_utility` | No description provided. |
| `test_a_temporarily_closed_amenity_is_not_offered` | No description provided. |
| `test_a_cleared_closure_leaves_the_amenity_bookable[None]` | `temporary_closure` is unconstrained jsonb, so SQL can ask whether it is null but not whether it is empty. Truthiness is the test the admin service already applies to the same column, and two readers disagreeing about whether the pool is shut is worse than either answer. |
| `test_a_cleared_closure_leaves_the_amenity_bookable[cleared1]` | `temporary_closure` is unconstrained jsonb, so SQL can ask whether it is null but not whether it is empty. Truthiness is the test the admin service already applies to the same column, and two readers disagreeing about whether the pool is shut is worse than either answer. |
| `test_a_cleared_closure_leaves_the_amenity_bookable[cleared2]` | `temporary_closure` is unconstrained jsonb, so SQL can ask whether it is null but not whether it is empty. Truthiness is the test the admin service already applies to the same column, and two readers disagreeing about whether the pool is shut is worse than either answer. |
| `test_the_catalogue_is_read_from_the_bookable_view` | Not `amenities`, and emphatically not `amenity_overview` -- reading the admin projection would put `outstandingDues` one column away from this response. |
| `test_the_query_filters_on_the_community_and_nothing_else` | The view has already applied `status`, `is_active` and the closure test, so tenancy is all that is left -- and it is the whole tenancy boundary, because `amenities` carries no RLS policy of its own. |
| `test_the_read_is_bounded_and_asks_how_much_it_left_behind` | The bound alone would truncate silently. The count is what lets the service tell a whole catalogue from a cut-off one. |
| `test_a_client_that_reports_no_count_is_read_as_a_whole_catalogue` | Not every SDK version surfaces `count`. Falling back to the rows in hand keeps the endpoint claiming exactly what it claimed before the count existed, rather than inventing a truncation that did not happen. |


## `test_resident_complaints.py`
The resident complaint surface -- six operations and one projection.

Three groups, kept apart because they answer different questions.

The **HTTP surface**: who may call each route, that the caller's own membership
is the only scope, and that a complaint belonging to someone else is
indistinguishable from one that does not exist. The repository is replaced, so
nothing reaches Supabase and the assertions are about arguments rather than rows.

The **projection**: what a `complaint_overview` row becomes on the wire, and what
a timeline event becomes as a sentence. Those go through the service directly --
routing a row shape through a request would put noise between the input and the
assertion.

The **query shape**: a recording stand-in for the Supabase client, asserting the
relation and the predicates. Everything above replaces the repository, so nothing
above would notice if the read were pointed at `complaints` instead of the view,
or if the ownership predicate were dropped -- which is the mistake that matters
most here.

*Total tests in this file: 59*

| Test Function | Description |
|---------------|-------------|
| `test_the_list_requires_a_session` | No description provided. |
| `test_a_resident_may_list_their_complaints` | No description provided. |
| `test_an_admin_listing_gets_their_own_complaints_not_the_queue` | The route is scoped to the caller whatever their role. One path that answers `mine` for one caller and `everyone's` for another is the shape 5.1 exists to prevent; the admin queue is `GET /dashboard/snapshot`. |
| `test_reopening_is_refused_to_an_admin` | Not because an admin could not press the button, but because reopening is the resident's verdict on the association's work. |
| `test_confirming_a_resolution_is_refused_to_an_admin` | No description provided. |
| `test_raising_requires_csrf` | No description provided. |
| `test_the_membership_comes_from_the_session_not_the_request` | No description provided. |
| `test_reading_one_complaint_is_scoped_to_the_caller` | The membership is part of the lookup, not a check afterwards. There is no code path in which "not yours" and "not there" could be told apart. |
| `test_someone_elses_complaint_is_a_404` | No description provided. |
| `test_raising_a_complaint_returns_the_created_complaint` | 201 and the detail, not an acknowledgement: the response carries the SLA deadline the database computed, which the client could not have known. |
| `test_the_urgency_is_translated_to_the_stored_priority` | No description provided. |
| `test_an_unknown_urgency_is_refused_rather_than_defaulted` | A silent default would file the complaint under a deadline the resident did not choose, and the form would show no sign of it. |
| `test_a_whitespace_only_title_is_refused_at_the_edge` | The database refuses it too, correctly. The model refuses it first, so the caller gets a 422 naming the field rather than one raised three layers in -- which is what `min_length` alone would have produced, since three spaces satisfy it. |
| `test_the_client_cannot_send_its_own_sla` | The rule the frontend store carries is a product decision applied in the database. A resident who could send this could send themselves a one-minute deadline. |
| `test_reopening_passes_the_reason_through` | No description provided. |
| `test_reopening_without_a_reason_is_refused` | No description provided. |
| `test_a_rating_outside_one_to_five_is_refused[0]` | No description provided. |
| `test_a_rating_outside_one_to_five_is_refused[6]` | No description provided. |
| `test_a_rating_outside_one_to_five_is_refused[-1]` | No description provided. |
| `test_confirming_without_feedback_is_a_complete_answer` | No description provided. |
| `test_marking_read_is_scoped_to_the_callers_own_membership` | Per membership, so an admin opening a complaint cannot clear the resident's marker. |
| `test_a_status_filter_is_translated_before_it_reaches_the_query` | And to **every** stored status that renders as the word asked for. `acknowledged` and `in_progress` both display as `In Progress`; a filter carrying only the second hides rows the same list shows under the caller's own word. |
| `test_filtering_by_resolved_finds_complaints_the_resident_has_closed` | `closed` renders as `Resolved` -- it is what a complaint becomes when the resident confirms it. Filtering with the write-side map would have returned a list missing exactly the complaints they had finished with, which reads as lost data rather than as a filter. |
| `test_an_unknown_status_filter_is_a_422_not_an_empty_page` | An empty page is what "you have no resolved complaints" looks like. A filter typo must not be indistinguishable from a true answer. |
| `test_the_unread_filter_reaches_the_query` | No description provided. |
| `test_a_later_page_offsets_rather_than_re_reading_the_first` | No description provided. |
| `test_has_more_is_true_while_rows_remain` | No description provided. |
| `test_an_empty_list_is_a_page_not_a_404` | No description provided. |
| `test_the_stored_status_becomes_the_frontend_word` | No description provided. |
| `test_closed_renders_as_resolved` | The frontend's select has three options and closed is not one of them. The database keeps a distinction the UI does not show. |
| `test_an_unknown_status_renders_rather_than_raising` | A status this map has not heard of means the enum grew. A complaint list that refuses to render is a worse answer than one optimistic row. |
| `test_the_priority_becomes_the_forms_urgency` | No description provided. |
| `test_an_unassigned_complaint_says_so` | No description provided. |
| `test_null_text_reads_as_empty_string_not_null` | No description provided. |
| `test_a_missing_category_falls_back_to_general` | No description provided. |
| `test_the_response_carries_no_internal_identifiers` | A resident shown a membership id learns an identifier they have no endpoint for, and `departmentId` is who inside the association is carrying the work. |
| `test_the_detail_extends_the_summary_rather_than_restating_it` | So a field can never be present in a list row and missing from the detail of the same complaint. |
| `test_a_status_change_reads_in_the_frontends_vocabulary` | Not `open -> in_progress`. The timeline is read by the resident, and the words on it should be the words on the rest of the screen. |
| `test_a_reopen_shows_the_residents_reason` | No description provided. |
| `test_a_comment_event_says_nothing_because_the_comment_is_in_the_thread` | No description provided. |
| `test_an_unknown_event_type_renders_an_empty_message_not_a_payload_dump` | A generic dump would put whatever a future writer stored -- including, one day, something not meant for the person who raised the complaint -- straight onto their screen. |
| `test_an_internal_comment_leaves_no_shadow_on_the_timeline` | `0020` writes a timeline event for every comment, internal ones included, and the policy on `complaint_events` scopes rows to the complaint rather than to visibility -- so the event reaches this surface even though the comment does not. A row saying a comment exists, leading to a thread where nothing new is visible, tells the resident something was said and refuses to say what. |
| `test_an_event_with_no_actor_label_reads_as_management` | No description provided. |
| `test_a_payload_that_is_not_an_object_does_not_break_the_timeline` | No description provided. |
| `test_an_event_carries_a_readable_heading_as_well_as_its_raw_type` | Both, not one. The client keys behaviour off `type`, which never changes; the resident reads `label`, which is free to. |
| `test_an_unknown_event_type_falls_back_to_the_type_as_its_heading` | A timeline that silently omits an entry is worse than one with an ugly row: the gap is invisible and the ugly row is a bug report. |
| `test_a_truncated_timeline_says_so_rather_than_looking_complete` | The one kind of truncation a client cannot detect for itself. |
| `test_a_complete_timeline_does_not_claim_missing_history` | No description provided. |
| `test_the_detail_puts_the_timeline_back_into_reading_order` | The repository reads newest-first so the bound keeps the recent end; the screen reads downwards. The reversal happens once, in the service. |
| `test_the_list_is_read_from_the_overview_view` | No description provided. |
| `test_the_list_filters_on_the_callers_membership` | Not the security boundary -- `0031` puts a policy on `complaints` -- but the difference between "mine" and "everything I may see". |
| `test_one_complaint_is_looked_up_by_id_and_owner_together` | No description provided. |
| `test_the_comment_thread_asks_for_public_comments_only` | The RLS policy is what makes it true. This predicate is what makes it obvious to the next person reading the query. |
| `test_the_timeline_reads_the_newest_end_even_though_it_displays_oldest_first` | The order and the bound are not independent choices. Ordering ascending and stopping at the limit keeps the *opening* of a long complaint and throws away everything since -- so on the one screen where the bound would ever bite, the resident sees a complaint frozen on the day they raised it. The service reverses these rows; the query keeps the end that matters. |
| `test_the_thread_reads_one_row_past_the_bound` | A read of exactly the limit cannot be told from a truncated one. The extra row is what turns `hasOlderEvents` into something measured. |
| `test_a_thread_longer_than_the_bound_reports_that_it_was_cut` | No description provided. |
| `test_a_thread_of_exactly_the_bound_is_not_reported_as_cut` | The off-by-one that would make every busy complaint claim missing history. |
| `test_the_service_raises_not_found_for_a_missing_complaint` | No description provided. |
| `test_the_service_refuses_an_unknown_status_filter` | No description provided. |


## `test_resident_home.py`
Notices, the flat, and the contact directory.

The assertion worth naming here is the household one. `household_overview` unions
two genuinely different things — people with accounts, and phone numbers that
belong to nobody in the system — and the prototype conflates them by
manufacturing a whole user row for a number. `source` is what keeps them apart on
the wire, so it is asserted rather than assumed.

*Total tests in this file: 15*

| Test Function | Description |
|---------------|-------------|
| `test_notices_require_a_session` | No description provided. |
| `test_adding_a_phone_requires_csrf` | No description provided. |
| `test_notices_are_scoped_to_the_callers_community` | No description provided. |
| `test_a_notice_carries_the_urgency_the_screen_renders` | The CHECK in `0018` stores lower case; `Notices.jsx` renders `Important`. Title-cased in the view, like every other vocabulary in this backend. |
| `test_a_category_filter_is_passed_through` | No description provided. |
| `test_a_blank_category_is_no_filter_at_all` | No description provided. |
| `test_there_is_no_resident_route_that_posts_a_notice` | Posting is an admin action and already exists elsewhere. A resident reaching it would be a resident publishing to the whole community. |
| `test_the_household_is_read_for_the_flat_the_residency_names` | From the residency, not from the session -- so this read and the write below cannot disagree about which flat is the caller's. |
| `test_a_caller_with_no_flat_gets_an_empty_list_not_an_error` | Staff have a membership and no residency. *Nobody* is a legitimate answer to "who lives in your flat". |
| `test_a_member_and_a_contact_are_told_apart` | The prototype invents a whole user row for a phone number. A system that did that for real would put somebody in the member count who cannot sign in and never agreed to join. |
| `test_the_flat_is_not_accepted_from_the_request_body` | A unit id in a body is a unit id somebody can change. It is resolved from the caller's own residency inside the RPC, and nothing here forwards one. |
| `test_adding_a_number_returns_the_whole_list` | The screen renders a list, and a client merging one row into it can merge it wrongly. |
| `test_an_empty_phone_number_is_refused` | No description provided. |
| `test_the_directory_is_the_communitys_departments` | §5.6. It stays current because admins maintain departments for reasons of their own -- which is the only kind of freshness that survives a committee. |
| `test_the_directory_carries_a_category_and_no_emergency_flag` | Deciding which categories mean *emergency* by matching strings would be a classification invented in the backend, wrong the first time somebody writes "Emergencies". |


## `test_resident_money.py`
The resident's money surface — four operations and two projections.

The group that matters most is the last. A payment endpoint has two properties no
ordinary response assertion catches: **a card number must not reach the
database**, and **a decline must not be an HTTP error**. Both are asserted
directly, because a test that reads the fields of a successful response cannot
notice either one going wrong.

*Total tests in this file: 31*

| Test Function | Description |
|---------------|-------------|
| `test_the_invoice_list_requires_a_session` | No description provided. |
| `test_paying_requires_csrf` | No description provided. |
| `test_an_admin_may_have_their_own_bills_too` | No role guard. An admin living in the community owes maintenance like anybody else, and the bills they get back are their own -- ownership being the view's `is_mine`, which is `is_own_invoice` itself. |
| `test_the_unpaid_tab_filters_on_the_word_the_screen_shows` | Not on `is_payable`. The two agree on every bill a resident normally has and part company on the ones that matter -- see the next test. |
| `test_the_paid_tab_is_paid_and_not_merely_unpayable` | `is_payable` is false for four different reasons -- paid, void, draft, and nothing outstanding. Defining the Paid tab as its inverse puts somebody's cancelled bill in the list of bills they have settled. |
| `test_no_view_returns_both` | No description provided. |
| `test_an_unknown_view_is_the_unfiltered_list` | No description provided. |
| `test_an_invoice_carries_both_vocabularies` | `Payments.jsx` splits on Unpaid and Paid and has no third branch, so `partially_paid` reads as Unpaid -- which is what it is to whoever owes the balance. The real one travels beside it. |
| `test_amounts_survive_as_decimals` | Money is never a float in this codebase. `0.1 + 0.2` is the reason. |
| `test_the_booking_list_is_the_callers_own` | No description provided. |
| `test_a_successful_payment_is_a_200_with_an_outcome` | No description provided. |
| `test_a_declined_payment_is_also_a_200` | §11.5. The request was well-formed, authorized, processed and produced a durable record; the *payment* failed. A 402 would put an ordinary business outcome in the same client branch as "your session expired". |
| `test_a_decline_is_still_written_to_the_database` | The difference between this and the admin's `record_payment`. A failed row is what a support conversation is reconstructed from, and it never enters a balance because every recomputation sums `succeeded` only. |
| `test_the_card_number_never_reaches_the_database` | Not "is masked before storage" -- *never sent*. §11.3. |
| `test_what_is_stored_is_a_receipt_line` | No description provided. |
| `test_the_response_never_carries_the_card_either` | No description provided. |
| `test_the_idempotency_key_reaches_the_rpc` | One key per press of Pay. It is what stops a double-tap paying twice, and the database is where it is enforced. |
| `test_a_missing_idempotency_key_is_refused` | A payment endpoint that accepts a request with no key is one that will charge somebody twice on a flaky connection. |
| `test_paying_by_card_with_no_card_is_refused` | No description provided. |
| `test_someone_elses_invoice_is_a_404` | Identical to one that does not exist. Ownership is part of the lookup rather than a check afterwards. |
| `test_the_settled_status_is_read_back_rather_than_assumed` | The invoice status after a payment is the database's answer -- the RPC recomputes it from the payments, and a client told what this function guessed would be told wrong the first time a partial payment existed. |
| `test_paying_a_booking_goes_through_the_booking_rpc` | `US-2.12`: payment and confirmation are one statement. Two calls here -- one to settle, one to confirm -- would be the exact failure the story describes. |
| `test_a_declined_booking_payment_leaves_the_booking_alone` | The half that gets forgotten. A failed payment must not leave a half-confirmed booking somebody believes they hold. |
| `test_a_replay_never_reaches_the_gateway` | The ordering is invisible with a pure simulator and is a double charge with a real provider behind the same seam -- which is the entire claim this module makes. The lookup comes first, and a hit ends the request. |
| `test_a_replay_is_described_from_the_row_that_recorded_it` | A retry carrying a card that would decline must still be told what happened, not what would have happened. Answering with the new verdict produces a body reading `failed` beside a `settledStatus` of `Paid`. |
| `test_the_key_is_looked_up_against_this_invoice` | The database refuses a key that already settled a different bill. The friendly answer -- hand back the other invoice's payment -- reports `succeeded` for an invoice that remains entirely unpaid. |
| `test_a_booking_replay_short_circuits_too` | No description provided. |
| `test_the_invoice_list_filters_on_the_write_paths_own_predicate` | `is_mine` is `is_own_invoice`, the function the settlement RPC calls. Filtering on `membership_id` is a *narrower* rule than the one that decides whether the payment will be accepted, and the gap between them is a bill the resident can pay and cannot see. |
| `test_one_invoice_is_fetched_through_the_same_predicate` | The read that produces the 404 and the read that fills the list have to agree about ownership, or a bill is payable from one screen and missing from the other. |
| `test_a_missing_title_reads_as_maintenance` | No description provided. |
| `test_a_null_amount_is_zero_not_none` | A screen that renders `null.toLocaleString()` is a screen that crashes. |


## `test_resident_snapshot.py`
The resident home aggregate.

Almost every assertion here is about a *rule*, not a field, because the fields
are other endpoints' and are tested where they live. What is only true here is
the arithmetic: which bill gets offered, whether a party of twelve counts as one
visitor or twelve, and whether the badge counts the feed or the page.

*Total tests in this file: 25*

| Test Function | Description |
|---------------|-------------|
| `test_the_snapshot_requires_a_session` | No description provided. |
| `test_staff_get_their_own_home_too` | No role guard. An admin who lives in the community owes maintenance and receives visitors like anybody else, and what comes back is theirs. |
| `test_tenancy_comes_from_the_membership_and_nowhere_else` | §5.2. The endpoint takes no parameters, so there is nothing a caller could send that would widen what comes back -- and a query string that looks like one is ignored rather than honoured. |
| `test_only_unpaid_bills_are_scanned` | No description provided. |
| `test_the_outstanding_total_is_the_sum_of_what_is_owed` | No description provided. |
| `test_the_maintenance_bill_is_the_one_offered` | `DashboardHome.jsx` looks for it by name: it is the recurring bill a resident opens the app to settle. |
| `test_without_a_maintenance_bill_the_oldest_is_offered` | Newest-first, so the last row is the oldest. Offering the newest would quietly hide an overdue bill behind a fresh one. |
| `test_an_unpayable_bill_is_never_offered` | The home screen's Pay button and the Payments page's Pay button are drawn from one column, so a bill the write path would refuse is never put behind one. |
| `test_a_total_that_could_not_be_summed_in_full_says_so` | A number that is quietly too small is worse than a number with a caveat: the resident pays what they are shown and believes they are square. |
| `test_a_resident_with_nothing_owing_gets_zero_not_null` | A screen that renders `null.toLocaleString()` is a screen that crashes. |
| `test_the_counts_are_guests_and_not_passes` | One pass for a party of twelve is twelve people at the gate. A card reading "1" in front of a resident expecting a dozen has misunderstood the question -- and `DashboardHome.jsx` reduces over `guestCount` for exactly this reason. |
| `test_approved_and_expected_are_counted_together` | To the resident they are one thing: a guest who has not arrived yet. |
| `test_a_guest_already_inside_is_not_still_expected` | No description provided. |
| `test_passes_awaiting_an_answer_come_back_whole` | The home screen approves and rejects from the card without navigating, so a title and a count would not be enough to act on. |
| `test_only_three_pending_passes_are_carried_but_all_are_counted` | The screen renders three. The count is what tells a resident there are more, which is the number they act on. |
| `test_a_visitor_awaiting_approval_is_not_counted_as_expected` | They are at the gate and have not been let in. Counting them among the expected would tell a resident somebody is on their way when in fact somebody is waiting on them. |
| `test_only_current_passes_are_read` | History is a tab, not a home-screen count. A guest who left last month is not somebody the resident needs to know about now. |
| `test_the_complaint_total_is_the_callers_own_count` | No description provided. |
| `test_notices_are_the_communitys_and_the_rest_is_the_callers` | The one part of this payload that is not personal. A notice board is a community fact, and it is scoped by community rather than by membership. |
| `test_the_badge_counts_the_feed_and_not_the_page` | A badge drawn from the returned events would read "1" for a resident with seven unread notifications, and would be wrong the moment anybody scrolled. |
| `test_the_activity_strip_is_the_notification_feed` | Not `member_activity`, which §5.7 reserved for it and which nothing in this project writes. §5.8 already made `notifications` the durable record of every user-visible event; a second log would be the pair of disagreeing feeds §5.7 set out to prevent. |
| `test_the_payload_says_when_it_was_assembled` | Six reads in sequence, not one transaction, so this is the only timestamp the response can honestly claim. |
| `test_an_empty_community_is_an_empty_snapshot_not_an_error` | A resident who moved in this morning has nothing anywhere, and every list is empty rather than absent -- a client that has to test for both is a client that will crash on one. |
| `test_a_pass_with_no_guest_count_still_counts_one_person` | `guestCount` of zero is a data problem, not an empty party. Counting it as nobody would make a visitor vanish from the card drawn to announce them. |
| `test_no_payable_bill_means_nothing_to_offer` | No description provided. |


## `test_resident_visitor_passes.py`
The resident visitor-pass surface -- six operations and one projection.

The group that matters most here is the third. Everything a visitor pass does
turns on **a secret appearing exactly once**, and that is a property no ordinary
response assertion catches: a test that reads a field cannot notice a field that
should not have been there. So there is a set below whose whole job is to assert
absence -- on the list, on the detail read, and on all three decisions.

The others follow the pattern of the complaint suite: the HTTP surface with the
repository replaced, the projection through the service directly, and a
recording stand-in for the Supabase client asserting what the query is pointed
at.

*Total tests in this file: 52*

| Test Function | Description |
|---------------|-------------|
| `test_the_list_requires_a_session` | No description provided. |
| `test_creating_requires_csrf` | No description provided. |
| `test_cancelling_requires_csrf` | No description provided. |
| `test_an_admin_may_hold_visitor_passes_too` | No role guard on this surface. An admin has visitors like anyone else, and the passes they get back are the ones they raised. |
| `test_creating_returns_the_security_code` | No description provided. |
| `test_the_list_carries_no_secret_on_any_row` | No description provided. |
| `test_reading_one_pass_back_carries_no_secret` | The QR screen's read. A resident who lost the code cannot recover it here -- that is the cost §5.4 accepts, and this is the test that keeps it paid. |
| `test_no_decision_response_carries_a_secret[approve]` | No description provided. |
| `test_no_decision_response_carries_a_secret[reject]` | No description provided. |
| `test_no_decision_response_carries_a_secret[cancel]` | No description provided. |
| `test_the_plaintext_code_is_never_sent_to_the_database` | Not "is hashed before storage" -- *never sent*. There is no statement log, slow-query log or replication stream in which it could appear. |
| `test_the_pass_token_is_hashed_the_same_way` | No description provided. |
| `test_two_passes_do_not_get_the_same_code` | A weak assertion on its own -- two draws from a CSPRNG could collide. It is here to catch the strong failure: a constant, or a code derived from the request, which is what a hurried implementation produces. |
| `test_the_code_is_drawn_from_the_csprng_not_the_random_module` | `random` is seeded and predictable to anyone who has seen a few outputs. For something that opens a gate, the module is the security property. |
| `test_the_validity_window_is_not_accepted_from_the_client` | A resident who could choose it could mint a pass valid for a year. The window is the community's TTL setting, applied in the database. |
| `test_the_expected_arrival_reaches_the_rpc` | No description provided. |
| `test_no_expected_arrival_leaves_the_default_to_the_database` | `None` rather than `now()` computed here: the pass is timestamped against the database's clock, which is the same one `validUntil` is measured from. |
| `test_a_guest_count_below_one_is_refused` | The slice does `Math.max(1, ...)` in the browser, which is a display default rather than a constraint. |
| `test_a_pass_can_be_created_without_a_name_because_the_form_has_no_name_field` | No description provided. |
| `test_the_derived_name_matches_the_label_the_prototype_builds` | `createVisitorsSlice.js` uses the free text when the purpose is `Other` and the selected option otherwise. One rule, and this is where it lives. |
| `test_other_with_no_detail_still_produces_a_name` | The column is `not null`; there is no input that may reach it empty. |
| `test_a_whitespace_only_name_derives_rather_than_failing` | Trimmed to empty by the schema, so it takes the same path as absent -- rather than a 422 about a field the caller was never asked to send. |
| `test_a_name_that_is_supplied_is_the_one_used` | The gate's own screen does collect a name. Nothing is derived over it. |
| `test_a_colliding_code_is_redrawn_rather_than_reported` | No description provided. |
| `test_the_redraw_is_a_new_code_not_the_same_one_again` | Retrying the same hash would be a slower way to fail the same way. |
| `test_the_token_is_not_reminted_with_the_code` | 32 bytes from the CSPRNG do not collide. Only the six digits are redrawn, so the QR handle a client is about to be handed stays the one that was minted for it. |
| `test_the_redraw_gives_up_rather_than_looping_forever` | An unbounded retry against a full code space is an outage, not a retry. |
| `test_a_conflict_that_is_not_a_duplicate_key_is_not_retried` | Every other conflict is a fact about the request, and a fresh code would not change it. |
| `test_each_route_sends_its_own_decision[approve-approve]` | No description provided. |
| `test_each_route_sends_its_own_decision[reject-reject]` | No description provided. |
| `test_each_route_sends_its_own_decision[cancel-cancel]` | No description provided. |
| `test_a_decision_reads_the_pass_back_rather_than_assuming_the_state` | No description provided. |
| `test_the_current_tab_filters_on_the_computed_column` | No description provided. |
| `test_the_history_tab_is_the_same_column_inverted` | No description provided. |
| `test_no_view_returns_both` | No description provided. |
| `test_an_unknown_view_is_the_unfiltered_list_not_a_422` | Unlike the complaint status filter, and deliberately. `view` is a tab selector with two known values; the honest answer to a third is everything, not a 422 about a parameter the caller did not mean to constrain. |
| `test_denied_reads_as_rejected` | The one status where the column and the screen genuinely disagree. Every view in the prototype says `Rejected`; the enum says `denied`. |
| `test_every_other_status_round_trips[expected-Expected]` | No description provided. |
| `test_every_other_status_round_trips[pending_approval-Pending Approval]` | No description provided. |
| `test_every_other_status_round_trips[approved-Approved]` | No description provided. |
| `test_every_other_status_round_trips[checked_in-Checked In]` | No description provided. |
| `test_every_other_status_round_trips[checked_out-Checked Out]` | No description provided. |
| `test_every_other_status_round_trips[expired-Expired]` | No description provided. |
| `test_every_other_status_round_trips[cancelled-Cancelled]` | No description provided. |
| `test_an_unknown_status_renders_rather_than_breaking_the_list` | No description provided. |
| `test_a_missing_purpose_reads_as_guest` | No description provided. |
| `test_a_lapsed_pass_is_surfaced_as_its_own_fact` | Still open, past its window. The client should say *lapsed* rather than leaving a resident to compare two timestamps. |
| `test_the_list_is_read_from_the_overview_view` | No description provided. |
| `test_neither_hash_is_ever_selected` | The columns exist on `visitor_requests`. They are not on the view, and they are not asked for -- so no refactor of this query can start returning one. |
| `test_the_list_filters_on_the_callers_membership` | No description provided. |
| `test_one_pass_is_looked_up_by_id_and_owner_together` | So a pass belonging to someone else cannot be told from one that does not exist -- not by status code, and not by response time. |
| `test_a_missing_pass_is_a_not_found` | No description provided. |


## `test_session_flow.py`
The browser session end to end: the redirect out, the redirect back, the
authenticated call, and logout.

**Why this file exists separately from the rest of `tests/api`.** Every other
file here uses `resident_api_client`, which overrides `get_current_user` and
`get_active_membership` with fixtures. That is the right seam for testing a
handler — it isolates the thing under test — but it means no test in this suite
has ever asked the question the resident portal actually depends on: *can
somebody who is not signed in reach one of these endpoints?* An override answers
"yes, because we told it to". Nothing overrides anything below: the token is a
real HS256 JWT, `decode_token` really verifies it, `get_active_membership` really
resolves tenancy, and `require_csrf` really compares the cookie against the
header. The only patched boundaries are the two the suite has always patched —
the Supabase network calls and the identity provider.

**The probe endpoint is `GET /resident/snapshot`**, chosen because it is the one
screen a resident lands on after signing in and because it depends on the whole
chain: `get_active_membership` for tenancy and `get_request_client` for a
token-scoped Supabase client. If the chain is wrong anywhere, this endpoint is
where a resident finds out.

Three properties are worth naming, because they are the ones that would be
invisible in a handler test and expensive in production:

* **A signed-out browser gets `401`, not an empty page.** The distinction that
  matters to the frontend is between *no session* (`401` — send them to sign in)
  and *a session with no community* (`403 active_membership_required` — send them
  to the Join/Create chooser). Collapsing the two is how a newly-registered user
  ends up in a redirect loop.
* **`?next=` cannot leave this origin.** An OAuth start that echoes an arbitrary
  `next` into the post-callback redirect is an open redirect wearing a login
  page, and it is the classic way a phishing link borrows a real domain.
* **Logout works when the access token has already expired.** Anything that
  verifies the token before clearing the cookies leaves the one user who most
  needs to sign out unable to.

*Total tests in this file: 27*

| Test Function | Description |
|---------------|-------------|
| `test_api_100_oauth_start_redirects_to_the_provider_with_a_bound_transaction` | No description provided. |
| `test_api_101_oauth_start_carries_the_requested_return_path` | No description provided. |
| `test_api_102_oauth_start_defaults_the_return_path_when_none_is_given` | No description provided. |
| `test_api_103_oauth_start_refuses_a_return_path_that_leaves_this_origin[https://evil.example/harvest]` | An open redirect behind a sign-in page is a phishing link with our domain on it. `safe_return_path` refuses rather than silently substituting a default, so a caller sending a hostile value learns it was rejected instead of being quietly signed in somewhere else. |
| `test_api_103_oauth_start_refuses_a_return_path_that_leaves_this_origin[//evil.example/harvest]` | An open redirect behind a sign-in page is a phishing link with our domain on it. `safe_return_path` refuses rather than silently substituting a default, so a caller sending a hostile value learns it was rejected instead of being quietly signed in somewhere else. |
| `test_api_103_oauth_start_refuses_a_return_path_that_leaves_this_origin[/\\evil.example]` | An open redirect behind a sign-in page is a phishing link with our domain on it. `safe_return_path` refuses rather than silently substituting a default, so a caller sending a hostile value learns it was rejected instead of being quietly signed in somewhere else. |
| `test_api_103_oauth_start_refuses_a_return_path_that_leaves_this_origin[http://localhost:5173.evil.example/]` | An open redirect behind a sign-in page is a phishing link with our domain on it. `safe_return_path` refuses rather than silently substituting a default, so a caller sending a hostile value learns it was rejected instead of being quietly signed in somewhere else. |
| `test_api_104_oauth_start_refuses_a_provider_that_is_not_enabled` | No description provided. |
| `test_api_105_oauth_callback_lands_on_the_frontend_and_establishes_the_session` | No description provided. |
| `test_api_106_oauth_callback_without_a_transaction_cookie_is_unauthenticated` | The cookie is the only thing binding a provider code to the browser that asked for it. Without it there is nothing to verify against, so a code replayed from elsewhere buys nothing. |
| `test_api_107_oauth_callback_refuses_a_transaction_signed_with_another_secret` | The destination is read out of the transaction cookie rather than the query string, so the signature is what stands between a forged cookie and a redirect to anywhere. Forging one with the wrong key must fail closed. |
| `test_api_108_oauth_callback_refuses_an_expired_transaction` | No description provided. |
| `test_api_109_oauth_callback_without_a_code_is_unauthenticated` | The provider sends the browser back with no code when the user cancels at the consent screen. It is a refusal, not a malformed request. |
| `test_api_110_a_resident_endpoint_refuses_a_browser_with_no_session` | No description provided. |
| `test_api_111_a_resident_endpoint_refuses_a_forged_access_cookie` | Signed with the right algorithm and the wrong key. `decode_token` verifies the signature rather than reading the claims, so this is a `401` and not a session belonging to whoever the `sub` claim names. |
| `test_api_112_a_resident_endpoint_reports_an_expired_session_distinguishably` | `token_expired` is the signal the client refreshes on. If it arrived as a generic `authentication_error` the browser would sign the user out on every hourly expiry instead of quietly renewing. |
| `test_api_113_a_signed_in_user_with_no_community_is_told_so_not_refused` | The case a newly-registered user is in for exactly as long as it takes them to join or create a community. It has to be distinguishable from *not signed in*, or the frontend sends them back to a sign-in page they have already completed and the loop never ends. `403` with `active_membership_required` is the frontend's cue to show the Join/Create chooser. |
| `test_api_114_a_signed_in_resident_reaches_the_handler_through_the_real_chain` | Nothing here is overridden: the cookie is verified, the membership is resolved from a row, and a token-scoped Supabase client is built. This is the test that fails if any link in the chain is rewired. |
| `test_api_115_the_membership_is_resolved_from_the_database_not_the_token` | A token claiming to be an admin changes nothing: the role comes from `community_memberships`. The claim below is ignored, and the resolved role is whatever the row says. |
| `test_api_116_a_bearer_header_authenticates_the_same_call` | The cookie is for browsers; the header is what the contract has always documented and what a non-browser caller uses. Both must reach the same place, or the OpenAPI security scheme is describing something that does not work. |
| `test_api_117_logout_clears_the_session_and_the_next_call_is_refused` | The property that matters is the second half. A logout that returns `200` and leaves a usable cookie behind is worse than no logout at all, because the user has been told they are signed out. |
| `test_api_118_logout_clears_the_session_even_when_the_provider_refuses` | Revocation is best-effort by design. If Supabase is unreachable, the local session must still end — otherwise a provider outage is also a security incident, because nobody in the building can sign out. |
| `test_api_119_logout_works_when_the_access_token_has_already_expired` | Logout deliberately does not depend on `get_current_user`. The user whose token expired while the tab was open is precisely the one who presses Sign out, and a logout that first verifies the token would refuse them. |
| `test_api_120_logout_refuses_a_cross_origin_caller` | Forced logout is a real nuisance attack, and `POST` with no body is the easiest thing in the world for another origin to submit. |
| `test_api_121_logout_refuses_a_csrf_token_that_is_not_bound_to_the_session` | The cookie and the header matching is not enough on its own — an attacker who can set a cookie can set both. The token is an HMAC of the access token, so one lifted from a different session does not verify against this one. |
| `test_api_122_logout_is_idempotent_for_a_browser_that_has_no_session` | Pressing Sign out twice, or landing on a stale tab, must not produce an error page. With no access cookie the pre-auth CSRF token is what authorizes the call, and the answer is the same `200`. |
| `test_api_123_the_whole_round_trip_signs_in_reads_and_signs_out` | Start, callback, an authenticated read, logout, and a refused read — in one client, with one cookie jar, in the order a browser does them. The individual steps are tested above; what this adds is that the cookies one step sets are the cookies the next step accepts. |


## `test_settings.py`
Community-settings validation API cases.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_api_015_settings_rejects_timezone_with_whitespace` | No description provided. |


## `test_system.py`
System and authorization-boundary API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_001_health_check_returns_environment` | No description provided. |
| `test_api_002_dashboard_snapshot_rejects_unauthenticated_request` | No description provided. |


