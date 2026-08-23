# API Tests Documentation

> **Note:** This file is generated from test docstrings by running `uv run pytest --collect-only --generate-test-docs` from `backend`.

## `test_access_requests.py`
Resident access-request and administrator-decision API cases.

*Total tests in this file: 5*

| Test Function | Description |
|---------------|-------------|
| `test_api_005_resident_creates_access_request` | No description provided. |
| `test_api_006_admin_approves_access_request` | No description provided. |
| `test_api_258_approving_a_registered_professional_says_which_rule_refused` | The trigger's own message reaches the administrator, with its own code.  Before this the approval path answered every database failure with "this access request cannot be approved" and the code ``access_request_not_pending``, which sends an administrator to look at a request that is pending and perfectly fine. The applicant is a registered service professional and needs a second account; nothing in the old answer could say so. |
| `test_api_259_an_unrecognised_approval_failure_keeps_the_generic_answer` | Postgres' own text can quote a row value, so only our codes pass through. |
| `test_api_260_a_registered_professional_cannot_file_a_join_request` | Refused where the person is, not days later in an administrator's hands.  The membership this request would create is refused by the database, so filing it can only ever end one way. Before this the applicant was told "pending", waited, and the failure landed on an administrator who can see neither the professional registration nor a reason. |


## `test_amenities.py`
Amenity-booking API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_007_partial_booking_cancellation_returns_cancelled_day_count` | No description provided. |
| `test_api_008_booking_cancellation_rejects_empty_date_selection` | No description provided. |


## `test_auth.py`
Authentication API cases.

*Total tests in this file: 7*

| Test Function | Description |
|---------------|-------------|
| `test_api_003_auth_methods_returns_configured_methods` | No description provided. |
| `test_api_004_refresh_timeout_returns_service_unavailable` | No description provided. |
| `test_api_005_sign_in_with_an_unconfirmed_email_is_refused` | No session cookie may be set for an address nobody has proven they own. |
| `test_api_006_resend_reaches_the_provider_and_reveals_nothing` | The route used to return its reassurance without sending anything. |
| `test_service_signup_intent_is_allowlisted_and_reaches_the_confirmation_redirect` | No description provided. |
| `test_unknown_signup_intent_is_rejected` | No description provided. |
| `test_api_007_email_confirmation_establishes_browser_session` | No description provided. |


## `test_complaint_routing.py`
Which department owns a complaint.

**What these tests can and cannot prove.** The routing rule itself —
category first, the resident's pick second, the triage queue third — is
`resolve_complaint_department` in `complaint_department_routing`, and it is
Postgres. It is stubbed here, so nothing below shows that a "Water leakage"
complaint reaches Plumbing. No test in this suite can — it has no database, and
that is the whole shape of what is unproven. The CI job that resets a local
Supabase and applies every migration could, and nothing there covers this yet.

What they do prove is the half that is Python, and it is the half where a
mistake is silent:

* the two writes carry the caller's **own** membership id, because both RPCs
  authorize against it and a router that passed a client-supplied one would
  hand the whole surface away;
* a decision word outside ``accept|reject`` never reaches the database;
* the department is **not** taken from the request body on the move, which is
  the one field whose presence would turn "move a complaint out of my
  department" into "take a complaint out of somebody else's".

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_api_248_a_department_queue_carries_its_open_request` | The screen must know a transfer was already asked for.  Without this field the only way to draw the button correctly would be to read the request list and join the two lists client-side -- and until that finished, a supervisor could file the same request twice and learn about it from a unique-index violation. |
| `test_api_249_the_status_filter_is_passed_through_not_applied_here` | Filtering in Python would mean reading every complaint to show ten. |
| `test_api_250_the_triage_queue_is_scoped_to_the_callers_community` | The community comes from the session, never from a query parameter.  There is no community id on this route and that is deliberate: it is the one input that would turn "my society's unrouted complaints" into "any society's" if a caller could supply it. |
| `test_api_251_a_resident_cannot_read_the_triage_queue` | It is every unrouted complaint in the society, including other people's. |
| `test_api_252_the_triage_queue_is_not_a_child_of_complaints` | It was, once, and `resident_complaints.py` swallowed it.  That router owns `GET /complaints/{complaint_id}`, and FastAPI matches across aggregated routers in registration order -- so `/complaints/ unassigned` resolved as a complaint whose id is the word "unassigned" and ran the resident's read against it. Declaring this route earlier would have fixed it and would have left the triage queue's correctness depending on which order two files are included in.  This test pins the shape rather than the ordering: the path is a sibling of `/complaints`, not a child, so nothing anybody adds later can capture it. |
| `test_api_253_assigning_uses_the_callers_own_membership` | `assign_complaint_department` authorizes against this id.  It is taken from the resolved session and never from the body. A router that accepted a membership id from the client would hand the entire surface to whoever could guess one. |
| `test_api_254_a_resident_cannot_move_a_complaint` | Including their own: which department fixes it is not theirs to decide. |
| `test_api_255_a_transfer_request_may_name_no_destination` | "This isn't ours" is worth saying without knowing whose it is.  A supervisor who knows a lift complaint is not plumbing usually does not know which department owns lifts, and requiring a destination would either silence them or make them guess -- and a guess here becomes somebody else's queue. |
| `test_api_256_an_unknown_decision_never_reaches_the_database` | Two words, and a 422 that names both.  The RPC checks this too. Checking it here as well is what turns a database error the client has to interpret into a message that says which words are legal. |
| `test_api_257_a_decision_may_override_the_suggested_destination` | The manager is the one being asked, and knows the society better. |


## `test_complaints.py`
Complaint workflow API cases.

The first two cases monkeypatch the service, which is the house pattern and the
right one for asserting routing, validation and status codes. It is also why two
real defects lived here undetected for months: the service called a repository
function that has never existed, and forwarded a `visibility` the database
rejects. **A test that replaces the thing under test cannot find a bug inside
it.**

So the last three cases deliberately let the real service run, replacing only the
repository beneath it. They are the ones that would have failed.

*Total tests in this file: 13*

| Test Function | Description |
|---------------|-------------|
| `test_api_009_admin_updates_complaint_progress` | No description provided. |
| `test_api_010_resident_comments_on_complaint` | No description provided. |
| `test_api_133_a_comment_reaches_the_database_as_public_not_as_resident` | The defect this case exists for.  `complaint_comments_visibility_check` allows `public` and `internal`. The request says `resident`, because that is what the frontend sends and what API.md documents. Forwarding it unmapped made every comment a 23514 -> 422 -- and `test_api_010` above passed throughout, because it replaced the service that does the translating. |
| `test_api_134_an_unknown_visibility_is_a_422_before_the_database_sees_it` | Previously a `409` -- the database's answer to a word it had never heard.  Raised in the service now, so the error can name the field. The repository stub records whether it ran, which is how the case proves the RPC is never reached rather than merely that the status code is right. |
| `test_a_resident_may_not_raise_from_the_admin_portal` | `require_admin`, and it must refuse before the RPC is called.  The RPC refuses a non-admin too -- it re-checks the role where the row is, because an endpoint guard is not a database guard. This case is about the other direction: that the guard is actually declared on the route, which is the failure nothing else in the stack would notice. |
| `test_an_unattached_complaint_carries_no_for_membership` | The amenity/common-area mode. `forMembershipId` absent is what makes the complaint admin-portal-only, and it is absent by being absent -- there is no `raisedVia` on the wire for a client to contradict it with. |
| `test_an_on_behalf_complaint_forwards_the_residents_membership` | The other mode, and the one field that selects it.  Which membership ends up owning the row is the database's derivation, not this layer's -- so what is asserted here is that the id survives the trip, unmodified and distinct from the caller's own. |
| `test_the_priority_reaches_the_database_in_the_columns_vocabulary[High-high]` | `complaints_priority_check` allows `low`/`medium`/`high`; the admin screen renders `High`. Both spellings are accepted and only one is stored -- the same translation the resident's `urgency` goes through, so the two portals cannot mean different things by the same word. |
| `test_the_priority_reaches_the_database_in_the_columns_vocabulary[low-low]` | `complaints_priority_check` allows `low`/`medium`/`high`; the admin screen renders `High`. Both spellings are accepted and only one is stored -- the same translation the resident's `urgency` goes through, so the two portals cannot mean different things by the same word. |
| `test_an_unknown_priority_is_a_422_before_the_database_sees_it` | Raised in the service so the error can name the field. Reaching the RPC with it would produce a `22P02` -- a 422 either way, with a message written for Postgres rather than for the person who typed it. |
| `test_a_trade_alone_is_a_valid_body` | `category` is optional exactly as it is on the resident's form.  A caller submitting `skillId` has an id, not a display string, and the RPC snapshots that trade's current name into `category` itself. Requiring the field here would make the admin's trade picker invent one -- and the string it invented would be the one stored, which is the mutable-display-name problem `20260813100000` removed. |
| `test_a_blank_title_is_refused_by_the_model_not_by_the_database` | Three spaces satisfy `min_length=1` without `strip_whitespace`, and would arrive at the RPC as the empty string it raises `23514` for. |
| `test_api_135_the_edit_carries_the_membership_the_request_already_resolved` | The other defect. The service used to call a repository function that has never existed in this codebase, so both writes raised `AttributeError` on their second line. The membership now arrives from the dependency graph, which resolved it before the handler body ran. |


## `test_contract_consistency.py`
Check API documentation and runtime responses for contract consistency.

*Total tests in this file: 1*

| Test Function | Description |
|---------------|-------------|
| `test_api_016_openapi_422_schema_matches_runtime` | No description provided. |


## `test_conversations.py`
The hiring conversation, from both ends.

The plan's verification for this step is **"RLS denies a non-participant"**, and
no in-process test can prove that: the policy runs in Postgres and these tests
replace the repository. What they *can* prove is the thing that would make the
policy irrelevant -- that the API never offers a path around it. So the guard
assertions here are about absence: no route reads a caller-supplied id to decide
who may see a thread, no filter widens what the policy allows, and the two reads
answer 404 rather than 403 so threads cannot be enumerated by their refusals.

The fixture overrides **only** identity, leaving ``get_active_membership`` live.
A membership guard creeping onto this router would run the resolver against the
sentinel client and fail the test -- which matters more here than anywhere else
in this feature, because the caller this router exists for may hold no
membership in the community whose department they are talking to.

*Total tests in this file: 9*

| Test Function | Description |
|---------------|-------------|
| `test_api_151_the_thread_list_is_one_inbox_across_every_community` | A service person hired by three societies talks to three departments and has one screen. Omitting `departmentId` passes `None` to the repository -- no community scoping anywhere in the request path -- and the policy is what makes the result theirs rather than everyone's. |
| `test_api_152_the_department_filter_narrows_and_cannot_widen` | `departmentId` reaches the query as a filter on top of the policy, never as the thing that decides visibility. A caller passing a department they have no part in gets an empty list rather than somebody else's threads -- which is why it is safe to take from the query string at all. |
| `test_api_153_a_thread_the_policy_hides_is_a_404_not_a_403` | The policy hides the row rather than refusing it, so the read cannot tell a stranger that a thread exists. A 403 here would make a department's conversations with every other provider enumerable by walking ids and reading which refusals came back. |
| `test_api_154_the_thread_read_returns_its_messages_in_one_response` | One response rather than two round trips, because 'a thread with no messages' and 'a thread you cannot see' are different answers -- 200 with an empty list and 404 -- and splitting the read would deliver them separately. `authorSide` is what a renderer switches on; the two sides live in two different tables and the view collapses that into one word. |
| `test_api_155_opening_a_thread_is_idempotent_and_returns_the_whole_thread` | There is exactly one thread per (department, provider) pair -- a unique constraint, not a convention -- so this is what a 'Message' button calls every time it is pressed. The response is the full thread because one that already existed already has messages, and the caller is about to render them. |
| `test_api_156_a_message_is_returned_as_stored_not_as_sent` | The body is trimmed by the RPC and the author's name and side are resolved from the thread, none of which the caller supplied. A client that appended its own request to the list would be showing a message that differs from what everyone else sees. |
| `test_api_157_an_empty_message_is_refused_before_the_database_sees_it` | `min_length` matches the CHECK in 0038, so a blank body is a 422 naming the field rather than a 422 naming a constraint. The repository is not reached -- asserted, because a validator that fires after the write is not a validator. |
| `test_api_158_a_non_participant_is_refused_by_the_database_not_by_this_layer` | The router declares identity only and the service contains no participation check, so the 403 a stranger gets comes from `post_conversation_message` raising HB403. That is the whole design: one definition of who is in a thread, next to the data, rather than a copy here that can drift from the policy enforcing it. |
| `test_api_159_posting_without_the_csrf_pair_is_refused` | No role guard on this router at all, so CSRF is the only thing between a cross-site form post and a message somebody did not send. |


## `test_department_hiring.py`
Hiring, from the department's side.

The case that matters most in this module is ``api_143``, and it is about a
thing the tests cannot see. **Accepting an application writes a membership and a
roster row atomically**, and that happens inside
``decide_service_application`` -- one transaction, in Postgres, replaced here by
a stub. No in-process test can prove atomicity; what these cases can prove is
that the API never offers a path around it. So the assertions are about what
reaches the RPC and what does not: one call, carrying the terms, with the
decision the caller asked for and no second write beside it.

``api_145`` pins the other half of the same idea from the authorization side.
The router guard asks whether the caller manages *anything*; only
``can_manage_department`` in the database asks whether they manage *this*. A
test that stubbed the RPC and asserted a 200 would be asserting that the guard
we do not rely on passed.

*Total tests in this file: 18*

| Test Function | Description |
|---------------|-------------|
| `test_api_142_the_candidate_list_says_which_skills_matched` | `matchingSkillNames` is the subset that put a candidate on this list; `skillNames` is everything they do. Showing only the second leaves a manager wondering why an electrician is offered for a plumbing department. |
| `test_api_143_accepting_makes_exactly_one_call_carrying_the_terms` | The hire. Membership and roster row are written together inside the RPC, so the only thing the API can promise is that it never writes them separately: one call, with the terms, and nothing beside it. |
| `test_api_144_a_rank_sent_by_a_stale_client_cannot_promote_anybody` | Nobody is hired above `member` through the serviceman path.  Until 2026-08-11 this request carried `rank`, and this case asserted that `head` was translated to the stored `manager`. The PO removed rank from this path entirely: leadership is provisioned by email, and somebody who registered as a service provider joins as a team member.  A field the model no longer declares is **ignored**, not rejected -- Pydantic defaults to `extra='ignore'`. That is the right failure for this rule and it is why the case is worth keeping rather than deleting: a browser holding a cached bundle that still sends `rank: 'supervisor'` must not produce a supervisor. It forwards nothing, and the RPC's own default settles it. |
| `test_api_145_a_manager_of_another_community_is_refused_by_the_database` | The router guard passes -- the caller manages something. Only `can_manage_department` knows they do not manage *this*, and it lives in Postgres, so the 403 arrives from the repository. Asserting the guard alone would be asserting the check we deliberately do not rely on. |
| `test_api_146_withdrawn_is_not_a_decision_this_endpoint_accepts` | A manager withdrawing an application instead of rejecting it would erase the record that they refused somebody. Withdrawal belongs to the side that opened the negotiation, and it has its own route. |
| `test_api_147_blacklisting_requires_a_reason` | Whoever eventually decides whether to revoke a bar needs to know what it was for. An unexplained permanent decision is one nobody can review. |
| `test_api_148_removal_carries_the_reason_in_the_body_not_the_url` | A POST rather than a DELETE, because nothing is deleted and because the reason is a note one person writes about another -- a query parameter would put it in every access log on the way. |
| `test_api_149_hiring_authorization_reaches_the_scoped_database_check` | Roster-ranked managers carry worker/security memberships, so the former membership-role guard could not distinguish them from ordinary members. The request reaches the request-scoped adapter; RLS/can_hire_for_department remains the authoritative same-department check. |
| `test_api_150_an_invitation_offers_a_job_title_at_member_rank` | An invitation offers a *job title*, and always at rank `member`.  It carried `rank` and `shift` until the 2026-08-11 ruling. Both are gone: leadership is provisioned by email through `staff-invitations` and never hired here, and `staff_assignments.shift` describes nothing the system reads -- work reaches a worker through the dispatch sweep or a supervisor, and a guard's rota is `security_shifts`.  `rank` is asserted as the literal `member` rather than `None`: the service layer sends it explicitly so the value this API intends is visible at the call site rather than inherited from an RPC default nobody reading the Python would see. |
| `test_api_216_approval_no_longer_gates_on_the_handover_and_forwards_the_date` | Until 2026-08-10 this test asserted a 409 while anything was booked. The product owner overturned that rule: the decision is the manager's, and approval *releases* the booked work to the dispatch pool instead of being refused for it. What the service owes now is faithfulness — the manager's `effectiveAt` reaches the database as the same instant, and no commitment count is consulted on the way. |
| `test_api_217_reassigning_without_a_successor_asks_for_the_best_candidate` | A null staff id is the *ordinary* case and means take whoever the dispatch ranking returns -- the same ranking auto-assignment uses. If the API filled in a default here, the handover would stop following the ranking the product owner asked it to follow. |
| `test_api_218_an_unknown_item_kind_never_reaches_the_database` | Two kinds, named in one place. The RPC would refuse a third with its own `22P02`, but the message a caller gets from here names both alternatives -- and no write is attempted for a request that cannot succeed. |
| `test_api_219_the_handover_list_is_read_only_after_the_departure_is` | Two clients, in order, and the order is the authorization. `staff_departure_items` is `service_role` only because it returns complaint titles; the caller's own client reads the departure first, so RLS decides whether they may see it at all. Reading the items first would hand a stranger a department's work list on a guessed uuid. |
| `test_api_220_a_departure_the_policy_hides_reads_no_items_at_all` | The other half of api_219. A manager of another community reaches this handler -- the router guard only asks whether they manage *something* -- and the RLS policy returns no row. The 404 has to happen before the service client is used, or the guard is decorative. |
| `test_api_222_the_employee_page_gets_the_roster_row_and_its_departure` | One read for the identity card. The row is the same shape the roster tab renders — one mapping, not two that drift — and `departure` rides along when one is pending or approved-for-a-date, because the page the termination notification lands on has to show what it is deciding. |
| `test_api_223_a_staff_id_from_another_department_is_a_404_not_a_leak` | The path's department is a scope. The same roster row fetched under a different department's URL must not render — a link that shows somebody from another department is a link that lies, and the schedule read below it would leak complaint titles across department lines. |
| `test_api_224_the_schedule_window_reaches_the_database_untouched` | `from`/`to` are forwarded as the same instants the caller sent. The calendar decides its own window; a service that clamped or defaulted it would make the page's "next week" button a lie. |
| `test_api_225_zero_coverage_is_an_answer_not_an_error` | The doc's words: *"If there are none, it says so."* An item nobody can take comes back with `candidateCount: 0` and a 200 — the decision screen renders a statement, not an error state. And the departure is read with the caller's client before the service client computes anything (the api_219 ordering). |


## `test_departments.py`
Department CRUD, which had no API-level test file until 0048.

That gap is why this module exists and it is worth naming: the admin
departments router has shipped nine operations since 0019 with coverage only of
``_staff_payload`` (``tests/test_department_mapping.py``) and two "is it in the
spec" assertions. Everything between the view and the wire -- which column
becomes which field, and what happens to the ones that are null -- was
unasserted.

The cases below are chosen for the seams where that has actually gone wrong.

``api_180`` guards the pairing rule (R23): the view returns names and ids
ordered the same way, and the wire carries both, so a screen can render a label
and send back an id without a lookup. Two arrays that stopped agreeing
positionally would be a bug no type checker sees.

``api_182`` is the one with history. ``department_overview`` matched
``rank = 'head'`` for the head lateral; ``0035`` migrated every such row to
``'manager'`` and forbade ``'head'``, so ``head_name`` was null for every
department in the API from ``0035`` until ``skills_and_categories`` fixed the
view -- and ``0035``'s own header claimed it had already made that fix. The test cannot
reach Postgres, so it does the half it can: pin that a head the view *does*
return survives the mapping, so the next time this breaks it breaks in SQL only
and the search for it starts in the right file.

*Total tests in this file: 9*

| Test Function | Description |
|---------------|-------------|
| `test_api_180_names_and_ids_arrive_paired_for_both_vocabularies` | R23: every label the wire carries comes with the id that names it.  The view orders both arrays the same way, so position `n` of `categories` and position `n` of `categoryIds` are the same thing. A screen renders the first and submits the second without a second request. `skills` and `skillIds` are the same rule applied to the vocabulary 0048 added -- and are asserted here so the new pair cannot quietly drift out of order while the old one holds. |
| `test_api_181_a_department_with_no_skills_reports_an_empty_list` | Skills are never inherited from categories, so empty is the normal case.  Every department that existed before 0048 has no skills and must not acquire any by accident -- least of all from its categories, which answer a different question. Null from the view has to become `[]` on the wire, not null, because the screen maps over it. |
| `test_api_182_the_head_survives_the_mapping` | `head` is the wire word; `manager` is what the column stores.  The view's head lateral matched `rank = 'head'` from 0019 until 0048, while 0035 had migrated every such row to `'manager'` and forbidden `'head'` -- so `headName` was null for every department, and 0035's header said it had already fixed the view it did not touch. That fault was in SQL, which these tests cannot reach. What they can do is hold the other half still: if `headName` ever goes missing again, this passing proves the mapping is not where to look. |
| `test_api_183_creating_with_no_categories_sends_an_empty_list_not_nothing` | The RPC distinguishes an absent key from an empty one.  A department with no categories is a real choice, and `categories` is therefore always sent. Dropping the key when the list is empty would mean "leave them alone", which on a create is a different -- and unaskable -- instruction. |
| `test_api_184_the_status_vocabulary_is_translated_not_passed_through` | `active`/`archived` is stored; `Active`/`Inactive` is what the wire says.  Two vocabularies for one fact, with the seam in `vocabularies.py`. A screen reading the storage word would render "archived" in a filter offering "Inactive" and match nothing. |
| `test_api_185_a_resident_cannot_read_the_department_admin_surface` | `require_admin` on the router, and it is the only thing standing here.  These routes resolve the community from the caller's membership rather than from the request, so a resident reaching them would be reading their own society's roster -- which is exactly the read the directory endpoint exists to serve in a redacted form. |
| `test_api_186_the_whole_guard_table_holds_for_a_manager` | **This test is the safety net for a change in how the router is guarded.**  `departments.py` used to carry `require_admin` at the router level. The manager portal needs to read its own department, and FastAPI cannot remove a router dependency for one route -- so the router now carries the *looser* `require_admin_or_manager` and four routes carry `require_admin` explicitly.  That inverts the failure mode. Before, forgetting a guard on a new route was harmless because the router caught it; now, forgetting one leaves it open to every manager in the community. So the table is asserted whole rather than per route, and a new endpoint added without `ADMIN_ONLY` fails here.  **The four `.../staff` routes this table used to cover are gone.** `PUT`/`POST /departments/{id}/staff` and `PATCH`/`DELETE /departments/{id}/staff/{staffId}` were retired: nothing had called them since the `0035` hiring flow replaced roster writes with applications, invitations, `POST .../members/{staffId}/remove` and `POST .../blacklist` (`department_hiring.py`), and `Departments.jsx` had not sent a non-empty `staff` array since. See the money-and-admins staff-writes verdict. |
| `test_api_246_the_department_read_answers_can_hire_for_this_caller` | The screen asks the same function the RPC applies, not a role check.  `can_hire_for_department` gives hiring to the department's own active manager -- by membership *or* by roster rank -- and admits community admins as a fallback **only while it has neither**. So the same admin may hire for one department and not the next, and no property of the caller can say which. Reimplementing that in the browser would be a second copy of a three-branch rule, and the copy is the one nobody notices going stale. |
| `test_api_247_the_list_leaves_can_hire_unanswered` | `null` means *not asked*, which is different from *no*.  It is one round trip per department and the list has no control that needs it. Defaulting to `false` instead would have told twelve screens that the admin may not hire for any of them. |


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


## `test_geo.py`
The location picker's address proxy.

Four things are tested, and only the first is about geocoding.

**That the upstream's payload never reaches the client.** Nominatim answers with
about thirty fields per result. Three cross this boundary. A test that asserted
"the response has a label" would pass on a handler that forwarded the lot, so
the assertions here are on the *exact* key set.

**That the usage policy is honoured**, because that is the only reason this
endpoint exists rather than a `fetch` in the browser: an identifying
`User-Agent`, one request per second, and a cache. All three are asserted from
the outside -- what the upstream *received*, and how often -- rather than by
reading module state, so an implementation that keeps the constants and stops
applying them fails.

**That an upstream failure is a 503 and not a 500.** The picker keeps working
without address search; the map pin is right there. A 500 would tell the client
that the request was wrong when it was not.

**That the guard is identity-only.** A service person registering and a founder
onboarding a community both need this and neither holds a membership yet, so a
membership guard creeping onto these routes would 403 exactly the callers the
feature exists for. The fixture therefore overrides identity alone.

*Total tests in this file: 13*

| Test Function | Description |
|---------------|-------------|
| `test_api_320_a_search_returns_three_fields_and_not_the_upstreams_payload` | Thirty fields go in and four come out. Asserted as an exact key set, because "it has a label" would also pass on a handler that forwarded the licence string, the OSM id and the bounding box. |
| `test_api_321_the_upstream_call_identifies_itself_and_asks_for_five_results` | Nominatim's usage policy asks for an identifying `User-Agent`, which a browser will not let script set -- so this endpoint existing at all is only justified while it sends one. |
| `test_api_322_the_same_search_twice_reaches_the_upstream_once` | Caching is a term of use, not an optimisation: a hundred servicemen registering in one suburb type the same three strings. Case and spacing are normalised before the key, so "Andheri  West" is the same question. |
| `test_api_323_two_different_searches_are_spaced_out_by_the_throttle` | One request per second is the documented absolute maximum, and the cache cannot help two people searching different things. The interval is shortened here so the assertion is about the mechanism rather than about waiting. |
| `test_api_324_an_upstream_429_is_a_503_the_picker_can_act_on` | Being throttled by somebody else's free service is a true statement about a third party, not a broken request. The screen still has a map pin, so the message says to use it. |
| `test_api_325_an_upstream_timeout_is_a_503_and_is_not_cached` | A failure must not poison the cache for a day. The retry after a timeout is the whole recovery path, and a cached error would remove it.  The throttle interval is shortened because the retry is genuinely subject to it -- a failed attempt still spent the second -- and a test that proved that by waiting would cost the suite a second to say what `test_api_323` already says. |
| `test_api_326_no_match_is_an_empty_list_and_not_a_404` | "Nothing found -- drop the pin instead" is a state the pick-list renders. A 404 would send the client down the branch that means the route is gone. |
| `test_api_327_a_one_character_query_is_refused_before_the_upstream_is_touched` | A one-character search matches most of the planet and would spend the one-per-second budget on nothing. |
| `test_api_328_an_unauthenticated_caller_is_refused` | The guard is identity-only, which is a narrowing and not an absence: this proxies a third party's free service under our name, and an open one would be a rate limit anybody could exhaust for everybody. |
| `test_api_329_a_reverse_lookup_names_the_dropped_pin` | The label is built from the address parts rather than from the head of `display_name`, which starts with a house number as often as not -- and the house number is exactly what this field must not carry. |
| `test_api_330_a_point_with_no_address_is_a_404` | Open sea. The client keeps the coordinate the person chose and leaves the label for them to write; nothing about the pin is invalid. |
| `test_api_331_an_out_of_range_latitude_is_refused` | Clamped at the route rather than passed through: this is the one place a caller can put an arbitrary value into an outbound URL. |
| `test_api_332_a_label_is_capped_at_the_length_the_column_accepts` | The database check is 120 characters. A label this API emits that could not then be saved is not a label, it is a form the person has to retype. |


## `test_leadership_exclusivity.py`
The three leadership rulings of 2026-08-21, at the seams the API owns.

    RULING 1  Leadership is invite-only and never from the marketplace pool.
    RULING 2  Leadership is exclusive to one community.
    RULING 3  Removal severs access completely.

**What these tests can and cannot prove.** Rulings 1 and 2 are enforced by
triggers and RPCs in ``20260821140000_leadership_exclusivity.sql``, and no test
in this suite runs Postgres. So the database half is asserted statically in
``tests/test_leadership_exclusivity_migration.py``, and what is asserted *here*
is the half the Python owns and is the half that has actually broken before:

* that the two new SQLSTATEs reach a caller as a 409 carrying a code they can
  branch on, rather than as an opaque 500 (``pg_errors`` is exercised for real,
  not stubbed -- the fakes raise what ``translate`` produces from a genuine
  ``HBMKT``/``HBLED``);
* that a refused claim does not cost anybody their session. That is not a
  hypothetical: ``_claim_staff_invitations`` swallows exceptions on purpose, so
  a claim that raises abandons *every* invitation in the loop silently, and the
  only way to tell the two designs apart from outside is that the refused
  person still gets a session and the department still sees the invitation;
* that ruling 3's snapshot read asks for active engagements only, so an account
  with an ended posting in one community and a live one in another sees exactly
  one.

Ruling 3's other surfaces -- the mailbox, the calendar, the feed -- are RLS and
are unreachable from here by construction. They are enumerated with their
verification queries in the migration's section 10.

**Added 2026-08-21, same day:** the refused invitee is now told why
(``20260821170000_blocked_invitee_notice.sql``). The write is SQL and is pinned
in ``tests/test_blocked_invitee_notice_migration.py``; what the API owns is the
*read* -- that the person-scoped, community-less, link-less row the claim files
comes back out of ``GET /notifications`` as the sentence the product owner
approved, rather than as a fallback title over an invented link.

*Total tests in this file: 16*

| Test Function | Description |
|---------------|-------------|
| `test_api_270_a_registered_provider_cannot_be_invited_as_leadership` | Ruling 1, refused where somebody is watching.  The trigger on ``staff_assignments`` would refuse this eventually -- at the claim, days later, with nobody at a screen. Refusing at the invitation is what turns "the manager we created never arrived" into a sentence the administrator reads while their hand is still on the mouse. |
| `test_api_271_a_second_leadership_invitation_is_refused` | Ruling 2, and a different code from ruling 1 on purpose.  Both are 409s. A client that must offer "hire them at technician rank instead" for one and "wait until they leave the other society" for the other cannot tell them apart from a status, and branching on the message text is what the custom SQLSTATEs exist to avoid. |
| `test_api_272_the_two_refusals_do_not_collapse_into_one_code` | The property the two tests above only imply when read together. |
| `test_api_273_an_invitation_after_the_previous_posting_ended_is_created` | Ruling 2 bounds *active* leadership, not leadership ever held.  "Being invited to a different community AFTER the previous leadership engagement has fully ended is legitimate and must keep working" is half the ruling, and it is the half a guard written as "has this person ever led" would break. Nothing is armed here, so the RPC accepts -- which is what an ended posting looks like from this side of the wire. |
| `test_api_274_a_blocked_invitation_says_why_in_the_pending_list` | The claim has no screen, so the pending list is where the answer lands.  Without this the row reads "waiting for first sign-in", which after a blocked claim is false: they signed in and were turned away. The status stays ``pending`` deliberately -- the situation is not terminal, and both existing verbs (correct the address, withdraw) still apply. |
| `test_api_275_a_supervisor_is_refused_a_marketplace_profile` | The mirror of ``api_270``, from the other side of ruling 1.  A supervisor holds a ``worker`` membership -- rank is not role -- so ``register_service_provider``'s older separate-account check deliberately lets them through: it refuses residents, managers and administrators. ``HBMKT`` is the refusal written for them, and the message says why there is nothing here for them rather than merely that they may not. |
| `test_api_276_a_refused_claim_does_not_cost_the_session` | The claim-time design, asserted as an outcome rather than a mechanism.  A registered provider whose email was invited as a supervisor signs in. The invitation must not take effect -- and the sign-in must still work. Under the rejected design (raise inside ``claim_staff_invitations``) the RPC would throw, ``_claim_staff_invitations`` would swallow it, and the observable result here would be identical *except* that any other legitimate invitation in the same loop would also have been abandoned. So what is pinned is what the API can see: the claim was attempted, nothing was claimed, and the caller ends up in the portal their provider row entitles them to rather than on an error page. |
| `test_api_277_nothing_claimed_is_not_reported_as_a_claim` | An empty result must stay falsy through the blocked path too.  ``get_session_context`` re-reads memberships only when the claim reports success. A blocked claim that reported ``True`` would make every sign-in by a refused invitee run the membership query twice, forever, and would look like a claim that keeps not sticking. |
| `test_api_278_a_claim_that_raises_still_leaves_a_session` | The backstop behind the design, kept honest.  The trigger is the guarantee and the in-function skip is the courtesy. If a path is ever found that reaches the trigger, the RPC *will* raise -- and the person must still get a session, because being refused an invitation is not the same as being refused an account. |
| `test_api_279_a_reinvitation_after_the_old_posting_ended_is_claimed` | The other half of ruling 2, at the claim.  Somebody whose supervision of community A has fully ended holds no active membership, so the session read reaches the claim -- which is exactly the path a *first* sign-in takes, and that is the point: an ended posting leaves the person indistinguishable from somebody who has never led anywhere, and community B's invitation lands normally. |
| `test_api_280_the_snapshot_shows_only_the_community_that_still_employs_them` | Ruling 3 on the one surface the BFF composes rather than the database.  Every other ruling-3 read is RLS. ``communities[]`` is not: it is assembled in Python from ``list_engagements_for_profile``, and it is what the supervisor's Complaints screen picks a department out of (``WorkerDashboard/Complaints.jsx`` 29-37). A single ended community-A row leaking into it would put community A's complaint queue on the screen of somebody who was removed from community A -- and the endpoint behind that queue is guarded by ``can_supervise_department``, so it would 403 rather than leak, which is a broken screen instead of a breach but is still not the answer.  Two assertions, and the second is the load-bearing one: the *request* is for active engagements only, so the filter is the repository's rather than a coincidence of the fixture. |
| `test_api_281_the_refused_invitee_reads_the_reason_in_their_own_feed[marketplace-Your invitation to join Blue Waters couldn't be applied. This account is registered as a marketplace service professional, and department leadership can't be combined with a provider profile. Ask the community to invite a different email address.]` | The gap this closes, from the only side that could see it.  Before 2026-08-21 the department was told three times -- `blockedReason` on the invitation, `blockedAt`, and a `staff_invitation.blocked` notification -- and the invitee was told nothing. They signed in, the invitation did not take, and the session read returned exactly what it returns for somebody nobody has ever invited (`api_276`). That contract is unchanged and must stay unchanged; the answer arrives out of band, here. |
| `test_api_281_the_refused_invitee_reads_the_reason_in_their_own_feed[elsewhere-Your invitation to join Blue Waters couldn't be applied because you already manage or supervise another community. Leadership is held in one community at a time \u2014 once your current engagement ends, the invitation can be applied on your next sign-in.]` | The gap this closes, from the only side that could see it.  Before 2026-08-21 the department was told three times -- `blockedReason` on the invitation, `blockedAt`, and a `staff_invitation.blocked` notification -- and the invitee was told nothing. They signed in, the invitation did not take, and the session read returned exactly what it returns for somebody nobody has ever invited (`api_276`). That contract is unchanged and must stay unchanged; the answer arrives out of band, here. |
| `test_api_282_the_notice_is_readable_with_no_community_behind_it` | Person-scoped, and that is not incidental.  A registered provider hired nowhere holds no membership at all, and a sitting leader holds one in a *different* community. `notify_member` would have filed this under whichever community was to hand, and ruling 3's own feed policy (`membership_is_live`) would then hide it the day that membership ended -- deleting the explanation for a refusal caused by that very posting. |
| `test_api_283_the_notice_offers_no_link_and_none_is_invented` | There is no screen for this, and a guessed one would be worse than none.  The invitee is not a member of that community and never becomes one; no portal lists invitations addressed to you, and the two refused populations land in different portals anyway. `notifications_service._FALLBACK_URLS` exists for four hiring kinds whose payloads carry the id a route needs, and its docstring is the rule being relied on here -- "a link that goes to the wrong screen is one the reader believes". `NotificationBell.openItem` marks an empty-url row read and navigates nowhere, which is the intended click. |
| `test_api_284_an_unrecognised_kind_still_renders_as_a_row` | The property that let this ship without touching the reader.  `render` reads `title`, `body` and `url` and nothing else, so a kind no Python file has heard of renders from its own payload. The fallback table is for writers that supplied no title; this writer supplies one, which is why `staff_invitation.not_applied` needed no entry -- exactly as the department's `staff_invitation.blocked` needed none. |


## `test_messages.py`
Direct messages: the chat dock's API.

Same posture as ``test_conversations.py``: the RLS policies and the SQL lock
run in Postgres and cannot be proven here, so these tests prove the API never
offers a path around them — the 404 that hides other people's threads, the
409 that surfaces the lock unchanged, the 422 that stops a subjectless open
before any write, and the counterpart resolution that is this service's one
piece of real shaping.

The fixture overrides **only** identity. The router must not grow a
membership guard: every portal mounts the dock, including a resident's.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_api_226_the_mailbox_resolves_the_counterpart_per_caller` | A thread stores its pair in canonical order; 'who is this with' depends on who is asking. The same row must answer differently for its two participants, and that resolution is this service's one real job. |
| `test_api_227_an_open_with_no_subject_or_two_never_reaches_the_database` | Exactly one subject: a person or a job. Both and neither are 422s decided in the service, so a request that cannot mean anything writes nothing. |
| `test_api_228_a_direct_open_without_a_community_is_refused_first` | The pair rule is per community — a manager here is a stranger there — so a direct open without the community that scopes it cannot be checked and is refused before the RPC. |
| `test_api_229_the_lock_surfaces_as_a_409_not_a_swallowed_error` | A finished job's channel refuses new messages — the protection the product owner asked for. The 409 is the feature; smoothing it into a 200 would reopen the line the lock exists to close. |
| `test_api_230_a_thread_the_policy_hides_reads_no_messages_at_all` | 404 covers missing and not-yours alike, and the message read happens only after the thread read succeeds — otherwise a guessed uuid pulls a transcript the policy meant to hide. |
| `test_api_231_a_sent_message_comes_back_as_the_database_stored_it` | The response is read back through the view rather than echoed from the request — the same _read_back discipline every write on this API keeps. |


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

The **HTTP surface** -- who may call, which *person* the query is scoped to,
what the response may not contain. The repository is replaced, and the
substitute records its arguments, which is how the recipient assertions are made.
Since `0041` the recipient is a profile: a service provider who has registered
and not been hired holds no membership anywhere, and the answer to their
application is a notification they have to be able to read.

The **projection** -- what a stored `payload` becomes. Those go through the
service directly: the interesting cases are payload shapes, and routing one
through a request would only add noise between the input and the assertion.

The **push configuration gate** -- that an environment with no VAPID keypair
returns 503 on the two endpoints that need one, and nothing else changes. That
is the whole of §10.5's "fail closed, but do not fail loudly", and it is the part
most likely to be broken by someone tidying the settings class later.

*Total tests in this file: 42*

| Test Function | Description |
|---------------|-------------|
| `test_the_feed_requires_a_session` | No description provided. |
| `test_a_resident_reads_their_own_feed` | No description provided. |
| `test_an_admin_has_a_feed_too` | `complaint.raised` and `access_request.created` are addressed to admins. A feed that refused them would mean building a second one later. |
| `test_the_recipient_is_the_signed_in_person` | The profile, not the membership. A caller in four communities has one feed and one badge, and a caller in none still has both. |
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
| `test_a_hiring_notification_gets_a_link_it_never_carried` | The five `0035` hiring kinds render a title and carry no `url`, so they have been arriving in the feed as text nobody could tap. Their payloads do carry the id the route needs, which is what makes this a fallback rather than a guess -- and the journal recorded it (5.18) rather than papering over it, so this is where the record is closed. |
| `test_a_writer_that_names_a_url_is_never_overruled` | The fallback is the last resort, not a rewrite. `0041` gave the invitation trigger a url of its own, and a table in Python that quietly replaced it would be a second opinion about where a notification goes. |
| `test_a_fallback_url_missing_its_id_yields_nothing` | A half-substituted path is worse than no path: a link that goes to the wrong screen is one the reader believes. |
| `test_the_vapid_key_is_served_to_a_member` | No description provided. |
| `test_the_vapid_key_requires_a_session` | Public by construction, but an unauthenticated endpoint that names our push key is free reconnaissance for no benefit. |
| `test_the_private_key_is_never_served` | No description provided. |
| `test_subscribing_accepts_the_browsers_own_document` | `PushSubscription.toJSON()`, posted unchanged. A transcription step is somewhere to put `auth` into the `p256dh` field, and that failure looks like a push that silently never decrypts. |
| `test_a_subscription_names_no_owner_at_all` | Nothing in the body says who this is for, and since `0041` nothing in the call does either -- the RPC reads `auth.uid()`. An owner argument would be a parameter that exists only to be validated against the session it came from, which is a forgery surface guarded rather than removed. |
| `test_a_subscription_without_keys_is_rejected` | No description provided. |
| `test_a_subscription_with_an_empty_encryption_key_is_rejected_before_storage[keys0]` | An empty browser key would create a subscription that can never decrypt.  This is deliberately a request-boundary test: the repository is never called, so an invalid browser document cannot replace a known-good device registration at the idempotent endpoint. |
| `test_a_subscription_with_an_empty_encryption_key_is_rejected_before_storage[keys1]` | An empty browser key would create a subscription that can never decrypt.  This is deliberately a request-boundary test: the repository is never called, so an invalid browser document cannot replace a known-good device registration at the idempotent endpoint. |
| `test_unsubscribing_takes_the_endpoint_in_the_body` | Not a query string: a push endpoint is a device identifier, and a request whose purpose is to stop tracking a device should not write it into every access log on the way. A `POST` to a sub-path rather than a `DELETE`, because content on a `DELETE` has no defined semantics and may not survive the trip. |
| `test_the_vapid_key_is_a_503_when_push_is_not_configured` | No description provided. |
| `test_subscribing_is_a_503_when_push_is_not_configured` | A subscription created against no keypair is bound to nothing, and the resident would have spent a notification permission prompt on a channel that can never deliver. |
| `test_unsubscribing_works_without_a_keypair` | Turning notifications off must not depend on an operator not having lost a key. |
| `test_the_rest_of_the_api_is_unaffected_by_missing_push_configuration` | Push is an enhancement. An unconfigured environment must not be a broken environment -- the same shape as `0024` no-opping without `pg_cron`. |
| `test_a_provider_with_no_membership_still_has_a_feed` | The answer to a job application arrives as a notification. A feed that required a membership would be empty for exactly the person waiting on one. |
| `test_a_provider_with_no_membership_can_clear_their_badge` | No description provided. |
| `test_a_provider_with_no_membership_can_turn_push_on` | Shipped broken on 2026-08-10: the worker profile screen offered a push toggle that posted to an endpoint requiring an active membership, so the one caller it was built for got a 403. The frontend cannot see a guard, which is why this assertion lives here. |


## `test_onboarding.py`
Founder and invitation activation regressions.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_founder_creation_verifies_identity_then_calls_onboarding` | No description provided. |
| `test_founder_identity_failure_is_an_authentication_response` | No description provided. |
| `test_invitation_redemption_verifies_identity_before_redeeming` | No description provided. |
| `test_invitation_identity_failure_is_an_authentication_response` | No description provided. |


## `test_remember_me.py`
The sign-in card's "Remember me" answer, end to end through the cookies.

The feature is entirely a question about *one header*: does the refresh cookie
carry a ``Max-Age``? Without one the browser drops it when the window closes and
the login page is there again, which is what someone on a shared machine expects.
With one, the returning visitor is silently signed back in.

Nothing else in the suite could catch a regression here, because every other auth
test asserts on the cookie *jar* -- and a jar shows the value, never the lifetime.
So these tests read ``Set-Cookie`` directly.

The companion ``hb_remember`` cookie is why ``/auth/refresh`` can keep the answer:
rotation re-issues the session cookies and has no other memory of what the user
chose. Logout has to clear it, or the next sign-in would inherit a decision made
by whoever used the browser last.

*Total tests in this file: 8*

| Test Function | Description |
|---------------|-------------|
| `test_remembered_sign_in_persists_the_refresh_cookie` | No description provided. |
| `test_sign_in_defaults_to_a_browser_session` | No `remember_me` in the body means the safe answer, not the sticky one. |
| `test_email_confirmation_never_persists` | The confirmation link never asked the question, so it cannot assume yes. |
| `test_refresh_preserves_the_original_answer[1-True]` | Rotation must not promote a browser session into a remembered one. |
| `test_refresh_preserves_the_original_answer[None-False]` | Rotation must not promote a browser session into a remembered one. |
| `test_logout_clears_the_remember_cookie` | Otherwise signing out would leave autologin armed for the next person. |
| `test_oauth_start_carries_remember_into_the_signed_transaction` | No description provided. |
| `test_oauth_callback_honours_the_remembered_transaction` | No description provided. |


## `test_request_timing.py`
Privacy-safe request timing and session cache-control contracts.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_request_timing_uses_the_route_template_not_query_values` | No description provided. |
| `test_session_responses_are_never_cacheable` | No description provided. |


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


## `test_resident_capability_guard.py`
The resident routes, seen from the admin who lives in the building.

`tests/test_resident_capability.py` pins the guard itself. This pins what the
guard did to the surface: which routes gained it, which deliberately did not,
and that an admin with a flat now reaches the handler on every route where the
answer is about their own home.

The residency lookup is a service-role read the API fixtures cannot satisfy, so
`tests/api/conftest.py` stubs it to *False* for the whole suite -- the fixture
memberships describe people with no flat, and only `resident_api_client` carries
a `unit_id`. `lives_here` is the opt-in for the caller this feature exists for.

*Total tests in this file: 14*

| Test Function | Description |
|---------------|-------------|
| `test_an_admin_with_a_flat_may_use_the_resident_verbs_on_it[/api/v1/complaints/complaint-id/cancel-body0-cancel_work]` | The bug this change fixes. Cancelling work in your own flat, reopening and confirming a resolution are verdicts about a home; the person who both runs the association and lives there was refused all three, because one membership row cannot say `admin` and `resident` at once. |
| `test_an_admin_with_a_flat_may_use_the_resident_verbs_on_it[/api/v1/complaints/complaint-id/reopen-body1-reopen]` | The bug this change fixes. Cancelling work in your own flat, reopening and confirming a resolution are verdicts about a home; the person who both runs the association and lives there was refused all three, because one membership row cannot say `admin` and `resident` at once. |
| `test_an_admin_with_a_flat_may_use_the_resident_verbs_on_it[/api/v1/complaints/complaint-id/resolution-body2-confirm_resolution]` | The bug this change fixes. Cancelling work in your own flat, reopening and confirming a resolution are verdicts about a home; the person who both runs the association and lives there was refused all three, because one membership row cannot say `admin` and `resident` at once. |
| `test_an_admin_with_a_flat_may_raise_a_complaint_about_it` | `POST /complaints` owns the complaint by the raiser's own membership and shows it on their resident portal, which only means anything for a membership that lives somewhere. |
| `test_an_admin_with_a_flat_may_answer_a_visit_proposed_to_them` | The scheduling router carries the guard at router level, so both of its routes move together. `respond_to_work_order_schedule` still checks `is_own_membership` in the same statement that would do the write -- this guard was only ever the early, clear error. |
| `test_staff_who_live_nowhere_are_still_refused[/api/v1/complaints-body0]` | The guard widened who counts as a resident; it did not stop asking. A department manager with no residency has no home for any of these to be about, and their complaints belong on `POST /complaints/admin-raise`. |
| `test_staff_who_live_nowhere_are_still_refused[/api/v1/complaints/complaint-id/cancel-body1]` | The guard widened who counts as a resident; it did not stop asking. A department manager with no residency has no home for any of these to be about, and their complaints belong on `POST /complaints/admin-raise`. |
| `test_staff_who_live_nowhere_are_still_refused[/api/v1/complaints/complaint-id/reopen-body2]` | The guard widened who counts as a resident; it did not stop asking. A department manager with no residency has no home for any of these to be about, and their complaints belong on `POST /complaints/admin-raise`. |
| `test_staff_who_live_nowhere_are_still_refused[/api/v1/complaints/complaint-id/resolution-body3]` | The guard widened who counts as a resident; it did not stop asking. A department manager with no residency has no home for any of these to be about, and their complaints belong on `POST /complaints/admin-raise`. |
| `test_staff_who_live_nowhere_are_still_refused[/api/v1/complaints/complaint-id/schedule-body4]` | The guard widened who counts as a resident; it did not stop asking. A department manager with no residency has no home for any of these to be about, and their complaints belong on `POST /complaints/admin-raise`. |
| `test_reading_stays_open_to_any_active_member` | `GET /complaints` and `GET /complaints/{id}` are scoped to the caller's own membership, so they answer "what have *you* raised" -- a question a member with no flat may still ask, and one whose answer is an empty list. |
| `test_marking_read_stays_open_to_any_active_member` | The marker is per membership, so clearing your own says nothing about anybody's home and cannot touch the resident's. |
| `test_a_resident_never_pays_for_the_residency_lookup` | The common caller short-circuits on the role. Asserted through the HTTP surface as well as in the unit tests because it is the property most easily lost by a later refactor that "simplifies" the two branches into one. |
| `test_csrf_is_still_checked_before_the_capability` | A guard that admits more callers must not admit more origins. |


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

*Total tests in this file: 63*

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
| `test_the_residents_department_guess_reaches_the_database` | The pick is a fallback, and a fallback that never arrives is no fallback.  `resolve_complaint_department` (`complaint_department_routing`) tries the *category* first and only reaches this when the category maps to no department -- so it decides exactly the cases the catalogue cannot: "Other", and anything nobody has mapped yet. If the field were dropped between the form and the RPC, the symptom would be complaints piling up in the admin's triage queue with nothing to say why. |
| `test_not_sure_sends_an_explicit_null_rather_than_nothing` | "Not sure" is the default answer on the form and the honest one.  It has to arrive as an explicit ``None`` -- that is what makes the third rule fire and lands the complaint in triage. Leaving the key out entirely would hand the decision to the RPC's own default, which is the same value today and is not the same contract. |
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
| `test_the_list_leaves_out_the_admins_own_community_complaints` | `raised_by_membership_id` alone stopped being enough on 2026-08-20.  An admin is also a resident -- one membership row per person -- so a complaint they raised about the lobby is *owned by the membership reading this list*. Without the second predicate every amenity and common-area complaint an admin has ever filed would appear in their personal "My Complaints", a list of things that happened to them at home.  The complement is the half worth stating: a complaint an admin filed **on a resident's behalf** is `raised_via = 'resident'` and does appear, on that resident's list, with their verbs intact. |
| `test_one_complaint_is_looked_up_by_id_and_owner_together` | No description provided. |
| `test_an_admin_portal_complaint_is_a_404_on_the_resident_detail_route` | The predicate is part of the lookup, not a check afterwards -- so an admin opening their own lobby complaint through the resident route gets the same answer as for a complaint that does not exist. Same reasoning as the ownership predicate beside it: a caller must not be able to tell "not on this portal" from "not there". |
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


## `test_resident_scheduling.py`
The resident's answer to a proposed visit.

Two routes, and the interesting property of both is what they do **not** accept:
a work-order id. The job is resolved from the complaint, so naming somebody
else's is not expressible rather than merely refused -- and the tests below
assert that by checking what the repository is asked for, since an endpoint that
took an id would have to be tested for every way of misusing it.

The other thing under test is the choice of *which* job. A complaint may carry
several over its life; the resident cares about the newest live one, and
returning simply the newest would let a cancelled retry hide the visit that
replaced it.

*Total tests in this file: 15*

| Test Function | Description |
|---------------|-------------|
| `test_api_176_the_proposal_is_looked_up_by_complaint_not_by_job_id` | The only id in the request path is the complaint's. A resident should not have to have read a work-order id to answer a question that was put to them, and an endpoint that accepted one would have to decide what happens when it names a different complaint's job. |
| `test_api_177_a_cancelled_retry_does_not_hide_the_visit_that_replaced_it` | Newest **live** one, not simply newest. The rows come back newest first, and the first terminal one is skipped -- otherwise a job cancelled an hour ago would be what the resident sees while a technician is on the way. |
| `test_api_178_a_complaint_with_no_live_job_is_a_404` | Nothing proposed, or everything proposed cancelled. Both are the same answer, and both are a 404 rather than an empty body -- a screen that got `null` would have to decide whether that meant "not yet" or "never". |
| `test_api_179_the_answer_is_confirmed_or_declined_and_nothing_else` | Declining is not a counter-proposal and there is no third answer. A resident who has changed their mind declines; a supervisor who has is the one who cancels. |
| `test_api_180_confirming_forwards_the_resolved_job_and_the_answer` | The work-order id the RPC receives was resolved here from the complaint, never sent by the caller. The response is the re-read row, so a screen sees the confirmation land rather than having to assume it. |
| `test_api_181_answering_twice_is_the_rpc_s_409_and_not_a_recheck_here` | The service does not look at the status before calling. Whether the job is still waiting is a question about a row, and by the time this process had read it and decided, a supervisor could have assigned somebody -- so the check is inside the transaction that does the write. |
| `test_api_182_answering_somebody_else_s_proposal_is_the_rpc_s_403` | `respond_to_work_order_schedule` checks `is_own_membership` against whoever raised the complaint. A neighbour in the same community passes every guard in this process and is refused there -- which is the whole reason the check is not duplicated here. |
| `test_api_183_staff_cannot_answer_on_the_resident_s_behalf` | Matching the precedent `resident_complaints.py` set for reopening and confirming a resolution: not because an admin could not press the button, but because this is the resident's verdict about their own home, and an admin answering for them is a record that says something untrue.  The guard is `require_resident_capability` since 2026-08-20, so what is refused here is an admin with **no flat of their own** -- which is what this fixture describes, and what `tests/api/conftest.py` stubs the residency lookup to say. The admin who does live in the building may answer, and `tests/api/test_resident_capability_guard.py` is where that is pinned. |
| `test_api_184_answering_without_the_csrf_pair_is_refused` | A cross-site form post confirming a visit somebody did not agree to is a small harm with a long tail -- a technician turns up to an empty flat and the slot is spent. |
| `test_api_373_the_read_says_which_question_is_being_asked` | `mode` is the derivation the screens would otherwise each make for themselves. A job with a slot is `approve` -- somebody proposed an hour and wants a yes or no; the same status with no slot is `pick`, and the card shows a time picker instead of two buttons. Deriving it on the client would put "is this a proposal or a request" in as many places as there are renderers, and the one that drifts shows the wrong control. |
| `test_api_374_picking_a_time_forwards_the_resolved_job_and_both_ends` | The work-order id the RPC receives was resolved here from the complaint, exactly as on the confirm route and for the same reason -- a resident should not have to have read one. Both ends go through: a half slot silently disables `work_order_assignments_no_overlap`, which is checked on `(start, end)` and does nothing when start is null. |
| `test_api_375_setting_a_time_the_association_already_proposed_is_a_409` | The two write routes refuse each other's jobs, and this is the half that matters most: a supervisor who proposed an hour asked a yes/no question, and answering it by overwriting the hour would silently turn their proposal into the resident's. The refusal is the RPC's, under the row lock, because the mode can change between a read here and the write. |
| `test_api_376_picking_a_time_on_somebody_else_s_complaint_is_the_rpc_s_403` | `resident_set_work_order_schedule` asks `is_own_membership` against whoever raised the complaint, the same question its sibling asks. A neighbour in the same community passes every guard in this process and is refused there -- which is why the check is not duplicated here. |
| `test_api_377_picking_a_time_with_no_live_job_never_reaches_the_database` | The job is resolved before the write, so a complaint whose only job was cancelled is a 404 from this process rather than an RPC call with a `null` id. Same answer as the read, deliberately: "nothing proposed" and "all of it called off" are the same fact to a resident. |
| `test_api_378_picking_a_time_without_the_csrf_pair_is_refused` | The same reasoning as the confirm route, one step worse: a cross-site post here does not merely agree to a visit, it books one at an hour the attacker chose. |


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


## `test_security_operations.py`
Gate operations: the guard, the credential, the reconcile and the export.

These cases pin the four things the migration alone cannot promise, and one of
them is the reason the module exists at all.

**The credential must never leave this process in plaintext.** ``0040`` compares
hash to hash and has no way to check that the caller hashed anything --
``verify_gate_credential`` would happily accept a six-digit string and simply
match nothing. So the assertion that the repository is handed a SHA-256 digest,
and specifically not the code the guard typed, is a property no SQL test could
make and no reviewer would notice the absence of.

**The router picks a gate membership rather than the default one.** A guard who
lives in one society and works the barrier of another has a default membership
of ``resident``, and ``require_membership_role`` would refuse them their own
register. The case that pins this puts the resident membership first on purpose.

**A refusal is a `200` with a verdict.** Turning *that code is not recognised*
into a `404` would split one act across the client's success and failure paths,
so it is asserted rather than left to a reader of the docstring.

**An export is a path from the gate to a spreadsheet formula.** Every text field
on these registers is typed by whoever is standing at the barrier, so a cell
beginning `=` is reachable by anyone who can walk up to it. The neutralisation
is asserted with the payload a real attempt would use.

*Total tests in this file: 20*

| Test Function | Description |
|---------------|-------------|
| `test_api_198_the_gate_membership_is_used_not_the_default_one` | The caller's *security* membership reaches the RPC, not their home one.  endpoint: POST /api/v1/security/gate/verify input_data: a caller whose default membership is `resident` elsewhere expected_output: the membership forwarded is the one holding a gate role |
| `test_api_199_a_caller_with_no_gate_role_is_refused_by_the_router` | A resident of one society and nothing else cannot read a register.  endpoint: GET /api/v1/security/material-movements input_data: a caller holding one `resident` membership expected_output: 403 community_role_required, and the repository untouched |
| `test_api_200_the_credential_is_hashed_before_it_reaches_the_database` | The six digits a guard typed never leave this process.  The single most important assertion in this module: `0040` compares hash to hash and cannot tell that the caller hashed anything, so nothing below the service would notice a plaintext code being sent -- it would simply match no row, which looks exactly like an unrecognised code.  endpoint: POST /api/v1/security/gate/verify input_data: the plaintext security code `483920` expected_output: the repository receives its SHA-256 digest and not the code |
| `test_api_201_an_unrecognised_code_is_a_200_with_a_verdict` | A refusal is an answer, not an error.  endpoint: POST /api/v1/security/gate/verify input_data: a code the database does not recognise expected_output: 200, verdict `not_found`, with the guard's sentence |
| `test_api_202_the_offline_bundle_carries_hashes_an_expiry_and_no_codes` | What a gate caches is hashes, scoped to a community, with a deadline.  endpoint: GET /api/v1/security/offline-bundle input_data: hours=6 expected_output: the requested window reaches the RPC, the community is the   gate's, the algorithm is named, and every pass carries a hash |
| `test_api_203_reconcile_is_per_entry_and_counts_replays_apart` | Each queued entry is its own call, and a replay is not an acceptance.  A replay counted as an acceptance would tell the security manager that a device admitted two people when it admitted one, and the number is the whole reason the endpoint answers with a summary.  endpoint: POST /api/v1/security/offline-reconcile input_data: three entries, one already reconciled and one refused expected_output: three calls, and the counts split 1/1/1 |
| `test_api_204_an_unknown_incident_category_is_refused_before_the_database` | A typed category does not quietly become *Other*.  Asserting the repository is **not reached** rather than only that the status is 422: a fall back to `other` would also produce a working request, and it is the silence that makes a report wrong rather than the status code.  endpoint: POST /api/v1/security/incidents input_data: a category nobody has ever offered expected_output: 422 unknown_incident_category, and no write attempted |
| `test_api_205_the_stored_incident_category_is_translated_both_ways` | The wire says `Fire alarm`; the column says `fire_alarm`.  endpoint: POST /api/v1/security/incidents input_data: the frontend's own display string expected_output: snake case reaches the RPC and the display string comes back |
| `test_api_206_a_return_date_on_a_non_returnable_item_is_refused` | The contradiction is caught in the service, not by a CHECK constraint.  endpoint: POST /api/v1/security/material-movements input_data: `isReturnable: false` with an expected return date expected_output: 422 not_returnable, and no write attempted |
| `test_api_207_scheduling_a_shift_forwards_the_terms_and_nothing_else` | One call, carrying the roster decision, with the gate membership on it.  No in-process test can prove the exclusion constraint refuses an overlap -- it runs in Postgres. What this proves is that the API reaches it rather than routing around it: nothing here checks for a clash first and nothing else is sent.  endpoint: POST /api/v1/security/shifts input_data: a guard, a window and a post expected_output: one `schedule_shift` call carrying exactly those |
| `test_api_208_a_shift_that_ends_before_it_starts_never_reaches_the_database` | The window is checked by the model, so the round trip is not spent.  endpoint: POST /api/v1/security/shifts input_data: an end before the start expected_output: 422, and no write attempted |
| `test_api_209_an_unknown_export_dataset_names_the_ones_that_exist` | One route, four datasets, and a fifth is a 422 rather than an empty file.  endpoint: GET /api/v1/security/exports/{dataset} input_data: a dataset nobody defined expected_output: 422 unknown_dataset, no read attempted |
| `test_api_210_an_export_is_csv_named_after_its_dataset_and_oldest_first` | The download a security manager opens for an audit.  Oldest first, unlike every list on this surface: a spreadsheet opened for an audit reads forwards through time, and re-sorting is the first thing the reader would otherwise do.  endpoint: GET /api/v1/security/exports/material-movements input_data: two entries, newest first as the view returns them expected_output: text/csv, an attachment filename, and the older row first |
| `test_api_211_a_formula_in_a_register_field_cannot_execute_in_a_spreadsheet` | Every text column here is typed by whoever is standing at the barrier.  Without the guard, an export is a path from *anyone who can walk up to the gate* to *code that runs when the security manager opens the audit*. `csv` quoting does not help -- the spreadsheet strips the quotes before evaluating the cell.  A leading `-` is prefixed too and a real number is not, which is the distinction worth pinning: stripping the character instead would silently turn a quantity of `-5` into `5`.  endpoint: GET /api/v1/security/exports/material-movements input_data: a description beginning `=` and a note beginning `-` expected_output: both neutralised with an apostrophe, the quantity untouched |
| `test_api_212_the_incident_list_renders_the_stored_category_for_a_screen` | A read translates too, not only a write.  endpoint: GET /api/v1/security/incidents input_data: a stored `fire_alarm` expected_output: `Fire alarm` on the wire |
| `test_api_232_the_roster_read_serves_the_shift_forms_guard_picker` | The picker gets names with ids, and the caller's gate membership is used.  endpoint: GET /api/v1/security/roster input_data: one active security-department staff row from 0047's function expected_output: camelCase entry carrying staffAssignmentId and name |
| `test_api_233_a_plain_guard_may_not_read_the_roster` | 0047 refuses below security manager, and the refusal reaches the wire.  endpoint: GET /api/v1/security/roster input_data: the repository raising the HB403 translation expected_output: 403 forbidden |
| `test_api_234_an_empty_roster_is_an_answer_not_an_error` | A community with no security department yet gets an empty list.  endpoint: GET /api/v1/security/roster input_data: 0047's function returning no rows expected_output: 200 [] |
| `test_api_235_a_shift_can_be_asked_for_by_id_without_naming_a_window` | `?shiftId=` reaches the repository on its own, with no range beside it.  This is what a guard arriving from `security_shift.assigned` (`0043`) sends. They hold an id and nothing else, and `0045` lets the shift that id names be weeks away -- so any window the screen guesses can miss it, and a window wide enough not to would risk being truncated by the 200-row cap before the row arrives. The filter has to travel alone.  endpoint: GET /api/v1/security/shifts input_data: `?shiftId=` and no `from`, `to`, `status` or `postId` expected_output: the repository receives that id and no range |
| `test_api_236_an_unknown_shift_id_is_an_empty_list_not_a_404` | A shift handed on again answers the same as a quiet fortnight.  Deliberately *not* a `404`. The list already answers `[]` for a window with nothing in it, and giving the id filter a different failure would turn this read into a way to test whether a shift exists in a community the caller cannot see. The screen tells the two apart from the parameter it sent, not from the status code.  endpoint: GET /api/v1/security/shifts input_data: an id no visible row carries expected_output: 200 [] |


## `test_service_providers.py`
A service person's own registration.

Two things are tested, and the first is the one that matters.

**That these routes need no membership.** Every other write surface in this API
resolves an active community membership first. These must not, because a person
who has registered but been hired nowhere holds no membership -- and a guard that
required one would 403 them out of exactly the screens that let them apply for
work. The fixture here therefore overrides *only* identity, leaving
``get_active_membership`` live: if a membership guard is ever added to one of
these routes, the resolver runs against the sentinel client and the test fails
rather than the product quietly becoming un-hireable.

**That the response is the database's answer, not the request echoed back.**
Three fields on a profile are not the caller's to choose -- ``skillNames`` comes
from the catalogue, ``communityCount`` is counted from live memberships, and
``serviceRadiusKm`` defaults in SQL -- so a write is asserted by what comes back
differing from what went in.

*Total tests in this file: 23*

| Test Function | Description |
|---------------|-------------|
| `test_api_124_the_skill_catalogue_is_readable_by_any_signed_in_caller` | `GET /skills` needs identity and nothing else -- no membership, no registration. Someone deciding whether to register has to see the trades before they have either. |
| `test_api_125_registering_returns_the_profile_the_database_settled_on` | The response carries `skillNames` and `communityCount`, which the request never contained. Echoing the request back would return everything except the answers. |
| `test_api_126_an_omitted_field_reaches_the_rpc_as_null_not_as_a_blank` | The RPC coalesces a null onto the stored value, so `None` is what makes a partial PATCH leave the other fields alone. Sending `""` would erase them. |
| `test_api_127_an_unregistered_caller_is_a_404_not_an_empty_profile` | "You are not a service provider" is a different answer from "you are one with nothing filled in", and the dashboard routes on the difference. |
| `test_api_128_the_skill_count_comes_back_from_the_database_not_the_request` | Ids naming a retired or unknown skill are dropped by the RPC rather than rejected, so a client sending three and being told one has learned something true about its stale list. |
| `test_api_129_the_offline_toggle_reports_what_the_database_settled_on` | Read back rather than echoed: a provider whose row is gone gets a 404 from the RPC, and one whose row is there gets the stored value. |
| `test_api_130_a_write_without_the_csrf_pair_is_refused` | These routes carry no membership guard, so CSRF is the only thing standing between a cross-site form post and someone's registration. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload0]` | No description provided. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload1]` | No description provided. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload2]` | No description provided. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload3]` | No description provided. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload4]` | No description provided. |
| `test_registration_rejects_incomplete_or_invalid_location_and_skills[payload5]` | No description provided. |
| `test_skills_cannot_be_replaced_with_an_empty_set` | No description provided. |
| `test_api_131_a_name_shorter_than_the_schema_allows_is_a_422` | Validated in pydantic as well as in the RPC. The duplicate is deliberate: the RPC's `22004` is the guarantee, and the 422 is the one that can point at the field. |
| `test_api_132_the_router_calls_the_service_it_imported` | Guards the wiring rather than the behaviour: a router that imported the module under a different name would pass every test above while calling nothing this suite has replaced. |
| `test_api_333_registering_carries_the_location_label_to_the_rpc_and_back` | The picker's whole output, end to end: a coordinate pair and a name for it.  The label reaches the RPC as its own argument rather than being derived server-side from the coordinates -- it is editable, so a person who drops a pin outside their own gate and types "Indiranagar" has said something the reverse geocode did not. |
| `test_api_334_a_blank_label_reaches_the_rpc_as_null_so_the_stored_one_survives` | The RPC coalesces null onto the stored value, and the column check refuses an empty string. Both are why "I cleared the box and saved" has to arrive as `None`: the alternative is a 422 for a gesture that meant nothing. |
| `test_api_335_a_label_longer_than_the_column_allows_is_a_422` | 120 characters is the database check, and it is a privacy boundary rather than a storage decision: a field that holds "suburb, city, state" and not a street address is what keeps this publishable on a hiring card. |
| `test_api_237_a_hiring_manager_reads_a_candidate_without_their_coordinates` | The read behind every "open this person" click on the hiring surface.  `latitude` and `longitude` are absent, and that is the case worth having: `service_providers_read` is `auth.uid() is not null`, so the view would hand a home coordinate to anybody signed in. `distanceKm` on the candidate list already answers where somebody is, measured from the community's own point, which is the question a manager actually has. |
| `test_api_238_a_resident_may_not_browse_the_service_directory` | `require_admin_or_manager` is the whole point of this route existing separately from a plain view read.  Postgres would return the row -- the read policy admits any signed-in caller, because a manager has to be able to find somebody they have never met. The guard here is what stops that being a directory of every tradesperson in the country, browsable by every resident with an account. |
| `test_api_239_the_literal_me_still_reaches_the_caller_s_own_profile` | Route ordering, asserted rather than assumed.  `/service-providers/{providerId}` is declared after `/service-providers/me` precisely so FastAPI matches the literal first. Reversed, `me` would arrive as a provider id -- and because the new route carries a role guard, an unregistered service person would get a 403 on their own settings screen instead of the 404 that sends them to the registration form. |
| `test_api_240_an_unknown_provider_id_is_a_404_not_an_empty_profile` | Same reasoning as `GET /me`: "there is no such person" and "there is a person with nothing filled in" are different answers, and a screen that rendered the second for the first would show a blank card with a hire button on it. |


## `test_service_signup_telemetry.py`
The launch funnel stores only allowlisted, anonymous events.

*Total tests in this file: 4*

| Test Function | Description |
|---------------|-------------|
| `test_event_is_allowlisted_and_cookie_identity_is_reused` | No description provided. |
| `test_every_event_reissues_the_visitor_cookie_so_its_window_slides` | The 30 days are 30 days of silence, not 30 days from the first event.  Written once, the cookie expires 30 days after ``cta_impression`` whatever the visitor does next -- so somebody who sees the CTA, waits five weeks and then signs up arrives as a *new* visitor. The funnel's denominator counts them and its numerator does not, and nothing about that is visible in the data. Re-issuing on every event makes the two agree. |
| `test_unknown_event_and_missing_csrf_are_rejected` | No description provided. |
| `test_storage_failure_never_blocks_the_funnel` | No description provided. |


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


## `test_skills.py`
Authoring the skill catalogue, and a community's categories.

The cases here divide into two ideas.

**The duplicate that must not be created.** Everything about this feature exists
to stop somebody typing "Plumbling" beside "Plumbing", and the mechanism is a
single boolean -- ``isExact`` -- computed in Postgres and never on the client.
``api_190`` pins it to the wire, and ``api_192`` pins the consequence: a name
that already exists comes back **200 with ``created: false``**, not 201 and not
an error, because somebody typing a trade that is already there has asked a
reasonable question. A test that accepted 201 either way would let the status
code become a polite fiction.

**The authorization the router does not do.** ``require_admin_or_manager`` only
asks whether the caller manages *something*. Whether they manage *this*
department is asked by ``can_manage_department`` inside each RPC, and the tests
cannot see it -- it is Postgres, stubbed here. So ``api_195`` asserts the shape
that keeps it reachable: the department id travels to the repository unchanged,
never resolved or defaulted in Python, because an id the API rewrote is an id
the database checked the wrong one of.

*Total tests in this file: 10*

| Test Function | Description |
|---------------|-------------|
| `test_api_190_a_suggestion_says_whether_it_is_an_exact_match` | `isExact` decides whether the form offers "add this as a new skill".  It is computed in Postgres and carried to the wire because the alternative -- comparing strings in the browser -- is a second implementation of a case- and whitespace-insensitive rule, and the two would disagree on exactly the input that matters. |
| `test_api_191_the_catalogue_read_is_unchanged_without_a_query` | The registration screen's grid must keep getting the whole catalogue.  `q` was added to an endpoint that already had a consumer. If a bare `GET /skills` started going through the search path it would silently truncate to `limit`, hiding trades from somebody choosing their own. |
| `test_api_192_an_existing_skill_comes_back_200_not_201` | Typing a trade that already exists is not an error and not a creation.  The status code carries the difference so a client can tell the two apart without parsing the body -- and so the body's `created` and the status code can never disagree. |
| `test_api_193_a_category_with_no_trade_is_reported_not_hidden` | A category matching no skill reaches no service person in any hiring search. That was true before this endpoint and invisible; the null is the whole reason the read exists, so it must survive serialization rather than being defaulted to an empty string. |
| `test_api_194_the_add_button_is_one_call_not_two` | Create-and-attach is a single RPC.  Two calls can half-fail, and the half that lands is a skill created and attached to nothing -- catalogue litter nobody asked for. So the API must not offer the two-step path even as an implementation detail: exactly one repository call, and it is the combined one. |
| `test_api_195_the_department_id_reaches_the_database_unchanged` | The only authorization that matters here runs in Postgres.  `can_manage_department` asks whether the caller manages *this* department; the router guard only asks whether they manage anything. That check is reachable only if the id in the path is the id the RPC receives, so an id resolved, defaulted or rewritten in Python would mean the database checked a different department from the one being edited. |
| `test_api_196_replacing_the_set_reads_it_back_rather_than_echoing` | The database is the authority on what landed.  An echo of the request would report success for ids the RPC dropped, which is exactly the case a caller needs to be told about. |
| `test_api_197_a_manager_of_another_department_is_refused` | `can_manage_department` raising HB403 must surface as 403, not 500.  The RPC is the only thing that can answer this, so the API's job is to let its refusal through with its meaning intact. |
| `test_api_198_a_resident_cannot_reach_the_authoring_surface` | The catalogue is global, so a careless guard here would let any member of any community write a word every other community then sees. |
| `test_api_199_a_blank_skill_name_is_refused_before_the_database` | `min_length=1` on the wire, and a matching check inside the RPC.  Both, deliberately: the schema keeps whitespace-only names out of the request, and the RPC keeps them out of a catalogue that another caller might reach another way. |


## `test_staff_provisioning.py`
Creating a manager or supervisor, and admitting them at sign-in.

This surface has no acceptance step, no token and nothing delivered, so the
usual assurances are absent: nothing bounces when the address is wrong, and
nobody confirms. What is left to test divides in two.

**The API half** — that a rank outside `manager|supervisor` never reaches the
database, that the email travels unmodified because it is the matching key
rather than a delivery address, and that claimed invitations stay in the list.

**The seam half** (`api_215` onward) — the more important one. A claim writes a
membership for somebody who had none, keyed on an email. Three properties keep
that from being a way in for the wrong person, and all three are assertions
about what the *Python* does rather than what the RPC returns:

* the email comes from `verified_identity`, never from the profile row or
  anything a client sent;
* the claim is attempted on **every** session read (`api_336`). It was attempted
  only when the caller held no membership until 2026-08-21, and that guard was a
  gap rather than an optimisation: a person who already belonged to a community
  never reached the claim, so their pending invitation was neither applied nor
  refused — it waited, invisibly, while the department that sent it saw
  `pending` forever;
* a failure inside it does not fail the session.

The RPC itself is Postgres and is stubbed here, so none of these tests prove a
membership is created correctly. They prove the API never offers a path to the
wrong one.

*Total tests in this file: 15*

| Test Function | Description |
|---------------|-------------|
| `test_api_210_the_email_reaches_the_database_unmodified` | The address is the matching key, not a delivery address.  Whoever signs in with it is admitted to this department. Any normalisation the API did on the way in would have to be repeated exactly at sign-in, in a different language, against a different value -- so the API does none, and the RPC's `lower(btrim(...))` is the single place it happens. |
| `test_api_211_the_response_is_read_back_not_echoed` | What comes back is what will be matched against, not what was typed.  The RPC lowercases and trims. Echoing the request would show an administrator `Manager@Example.COM` while the database waits for `manager@example.com` -- and on this endpoint that difference is the entire feature, because nothing else will ever tell them which one is real. |
| `test_api_212_member_is_not_an_invitable_rank` | `member` is reached only by hiring a registered service provider.  Allowing it here would rebuild the typed-in technician the department form just removed, by a different door. |
| `test_api_213_claimed_invitations_stay_in_the_list` | An administrator needs to know the manager they created has arrived.  A list that dropped each person at the moment they signed in would look identical whether somebody was still expected or had been working a month -- and "still pending after two weeks" is the only signal a mistyped address ever produces. |
| `test_api_214_a_resident_cannot_provision_leadership` | This endpoint mints a membership for somebody who has none.  It is the single most consequential write on the department surface, and the router guard is the first of the two things standing in front of it. |
| `test_api_241_a_mistyped_address_can_be_corrected` | The correction is the whole answer to this surface's one failure mode.  Nothing is mailed, so a wrong address produces no bounce -- only an invitation that never gets claimed. This is what an administrator does once the pending list has made that visible. |
| `test_api_242_an_omitted_field_is_left_alone_not_cleared` | `None` reaches the RPC, which reads it as "leave alone".  This is the difference between a PATCH and a PUT and it matters here for a concrete reason: the form that fixes an email is the same form that carries the job title, and a caller sending only the field they changed must not silently blank the rest. The nulls are sent rather than omitted so that the Python and the SQL agree on what absence means. |
| `test_api_243_the_correction_is_read_back_not_echoed` | Same reason as `api_211`, and more pointed.  The purpose of this call is to answer "is the address right now?". Echoing the request would answer "is the address what I just typed?", which the administrator already knows. |
| `test_api_244_the_department_cannot_be_moved` | A department in the body would be an authorization hole, not a field.  `can_manage_department` is checked against the invitation's *current* department, so honouring a new one would let the manager of department A mint staff into department B. Pydantic's default `extra='ignore'` means a client sending it is not refused -- it is simply not listened to, which is the safe half of that default and worth pinning down. |
| `test_api_245_a_resident_cannot_correct_an_invitation` | Editing the address is editing who gets admitted.  It carries exactly the consequence of creating the invitation, so it is guarded exactly the same -- the router refuses before the RPC is reached. |
| `test_api_215_the_claim_uses_the_verified_email_not_the_profile_row` | The email IS the authorization, so it must come from GoTrue.  `profiles.display_email` is an ordinary table. Trusting it would make a row a credential -- anything able to write that column could admit itself to any department that had been provisioned for that address. |
| `test_api_216_a_failed_claim_does_not_fail_the_session` | Claiming is an enhancement to a session that is already valid.  Somebody provisioned who meets a database error should land on the account page and be admitted on their next sign-in -- not be refused a session they are entitled to, which is what raising here would do to every request they make. |
| `test_api_217_nothing_to_claim_reports_nothing` | An empty result must not read as a claim.  `get_session_context` re-reads memberships only when this returns True. A truthy empty list would make every membership-less sign-in run the membership query twice, forever. |
| `test_api_261_the_provisioned_manager_is_admitted_by_the_session_read` | The claim, called the way production calls it -- with a `Profile`.  `api_215`-`api_217` hand `_claim_staff_invitations` its argument directly, so they were free to invent its shape, and they invented a dict. The only real caller is `get_session_context`, which holds whatever `profiles_repository` returns, and that has always been the `Profile` model. Reading it with `.get()` therefore raised `AttributeError` *before* the deliberate swallow inside the claim -- so the failure did not degrade to "no claim this time", it took down `GET /api/v1/auth/session` with a 500 for every signed-in user, on every request, whatever their intent.  Nothing above this line would have noticed: no test called `get_session_context` at all. This one does, and asserts the outcome the claim exists to produce -- a manager who has never signed in before lands in their portal on their first sign-in. |
| `test_api_336_a_sitting_member_still_gets_their_invitation_processed` | The claim-pass gap, closed. Product ruling 8, 2026-08-21.  `_claim_staff_invitations` sat inside `if not rows:` — the branch that had already established the caller holds no membership. So the whole population that *does* hold one never reached it: a resident invited to supervise a department, a worker on one community's roster invited to manage another, a supervisor being promoted. Their invitation was neither claimed nor refused. It stayed `pending` and the department that sent it kept seeing `pending`, with nothing anywhere reporting a problem.  Since `20260821140000`/`20260821170000` the refusal half matters as much as the claim half: an invitation that *cannot* be applied is marked `blocked` and both the department and the invitee are told — and that announcement was reachable only by people with no membership.  What is asserted is the call, not the outcome, because the outcome is the RPC's and the RPC is Postgres. The caller here holds a membership from the first read and the claim is attempted anyway. |


## `test_supervisor_actions.py`
The supervisor's card actions: resolve, priority, notes, chat, force-assign.

**What these tests can and cannot prove.** Every decision worth making lives in
`20260822170000_supervisor_actions.sql`: whether a running job blocks a resolve,
whether the priority has anywhere left to go, whether a second supervisor may
write in a thread the first one opened. Those are Postgres, they are stubbed
here, and the static battery in `tests/test_supervisor_actions_migration.py` is
the half that reads them.

What is proved below is the half that is Python, and it is the half where a
mistake is silent rather than loud:

* **the three body-less verbs declare no request model.** The house `post()`
  helper always sends `{}`, so a required model would answer 422 to every press
  of a button that has nothing to say -- the same trap take-up avoided, restated
  three times because it is three routes;
* **`force` routes to a different RPC and nothing else changes.** The default
  path must still call `assign_work_order` with exactly the arguments it always
  did: an offer that quietly became a booking would take a worker's right to
  decline away without any error anywhere;
* **the refusals come out of the database with their own sentences.** "Somebody
  is working on this right now" and "already at the highest priority" are what a
  supervisor reads, and `pg_errors` passes a custom code's message through
  untouched;
* **the staff detail read no longer refuses the department at the door.** The
  guard widened from `require_admin` to active membership because the RPC has
  always decided `is_community_admin OR can_supervise_department` for itself.

*Total tests in this file: 17*

| Test Function | Description |
|---------------|-------------|
| `test_api_353_resolving_needs_no_body_and_refuses_none` | **The route declares no request model**, for take-up's reason: the house `post()` helper always sends `{}`, and a required body would answer 422 to every press. Both an empty object and no body at all are a 200. |
| `test_api_354_a_running_job_refuses_the_resolve_in_the_rpc_s_own_words` | Ruling A2's refusal, and the reason nothing in Python pre-reads the jobs: "is anything running?" is asked under a row lock inside the RPC. A check here would be a second answer computed a moment earlier, against the caller's RLS rather than the RPC's, and it would disagree exactly when it mattered. |
| `test_api_355_an_unknown_complaint_is_a_404_and_a_stranger_s_is_a_403` | Both refusals reach the caller unflattened. A 403 rendered as a 500 -- which is what an unmapped SQLSTATE does -- is the one failure a supervisor cannot act on, because the sentence the RPC wrote never arrives. |
| `test_api_356_the_new_priority_comes_back_in_the_wire_vocabulary` | The RPC answers `high` and the supervisor reads *High*, through `app/domain/vocabularies.py` -- the one place this codebase maps a stored word to a rendered one. A `case` in SQL would be a second copy of that table in a language nobody would look in. |
| `test_api_357_a_complaint_already_at_high_is_a_409` | One way only, and the top is a refusal rather than a silent no-op. A supervisor who pressed the button and saw nothing change would press it again; the sentence is what stops that. |
| `test_api_358_a_note_is_created_and_its_bounds_are_checked_before_the_database` | `201`, because a note is a thing that now exists on a timeline.  The 1--2000 bound is stated twice on purpose: Pydantic answers an empty composer with a 422 naming the field, and `add_complaint_note_internal` answers `HB422` for any caller the API does not own. The note is trimmed here, so a body of spaces is refused rather than stored. |
| `test_api_359_an_internal_note_never_reaches_the_resident_s_timeline` | Ruling A5, at the only layer that can enforce it.  The RLS policy on `complaint_events` scopes rows to the complaint and not to a payload flag, so the row *does* reach this service -- and dropping it here is the whole of what keeps it off the resident's screen. The admin's resident-visible note carries no flag and must survive the same filter, which is the half of this test that would fail on an over-eager fix. |
| `test_api_360_the_priority_timeline_line_is_the_approved_copy` | The resident-facing sentence, rendered from the payload's *stored* words.  The RPC writes `{"from": "medium", "to": "high"}` because nothing in SQL translates a vocabulary; the sentence says *High* because `complaint_priority_to_wire` is asked here, in the same call every other complaint surface makes. |
| `test_api_361_opening_a_chat_returns_only_the_thread_id` | `200` and `{ threadId }`, not the thread.  The dock already fetches a thread and its messages from `GET /messages/threads/{id}`; returning the whole thing here would be a second projection of it, free to disagree with the first. `200` rather than `201` because the common case is *getting* the thread that exists -- a status code that alternated would describe the database's history rather than the caller's request. |
| `test_api_362_a_complaint_with_nobody_to_talk_to_is_a_409` | A conflict and not a 404: the complaint exists, and what is missing is a second person to put in the thread. The same shape `open_work_order_thread` already uses for a job with no worker-and-resident pair. |
| `test_api_363_a_worker_membership_reaches_every_action` | The claim the whole surface rests on: a department supervisor holds a `worker` membership, rank is not role, and the coarse router guard therefore has to admit every worker. What they may do to *this* department's complaint is `can_supervise_department` in Postgres. |
| `test_api_364_a_resident_reaches_none_of_them` | The other half of the same table. The person whose flat the leak is in has their own screens, and none of these is one of them -- refused before any query runs. |
| `test_api_365_every_action_is_refused_without_the_csrf_pair` | All four change something a resident or a worker can see, so CSRF is checked before the role guard has anything to say. |
| `test_api_366_assigning_without_force_is_the_offer_flow_unchanged` | The default path must reach `assign_work_order` with exactly the arguments it always did, and must not reach the forced one at all.  This is the assertion that matters most in the file. An offer that quietly became a booking would take a worker's right to decline away, and nothing anywhere would error. |
| `test_api_367_force_routes_to_the_force_assign_rpc_and_carries_the_slot` | `force: true` is the supervisor's override of the consent model, and it carries the same optional slot the offer does -- the supervisor picked the person and the hour in one gesture, and a second call to set the time would be a booking that briefly had none. |
| `test_api_368_a_forced_assignment_still_refuses_a_double_booking` | Forcing overrides the *worker's* consent, not physics. The overlap constraint is the same one the offer path meets, and the refusal names the person -- which is the whole reason the RPC checks it in words before the constraint checks it in `23P01`. |
| `test_api_369_the_staff_detail_read_admits_the_department_not_only_the_admin` | The eye popup's read. `require_admin` was refusing a department's own supervisors at the door, before `staff_complaint_detail` -- which has decided `is_community_admin OR can_supervise_department` since it was written -- could be asked. Widening the router guard to active membership does not widen who may read anything: the RPC answers `HB404` to everybody else, and a stranger walking complaint ids still learns nothing. |


## `test_supervisor_triage.py`
The supervisor's triage dashboard: one read and one verb.

**What these tests can and cannot prove.** The bucketing itself --- *live*,
*engaged*, taken up but undispatched --- is `supervisor_triage_snapshot` in
`20260822120000`, and it is Postgres. It is stubbed here, so nothing below shows
that a job with an outstanding offer lands in `assignedPending` rather than
`takenUp`. No test in this suite can: it has no database. That half is
`tests/test_supervisor_triage_migration.py`, statically, and the SQL editor after
the file is applied.

What they do prove is the half that is Python, and it is the half where a mistake
is silent:

* the four arrays are rendered **in the order and grouping the RPC returned
  them**. The frozen contract says the server buckets and the client does not
  re-derive, and a service that filtered here would be a fifth definition of
  *engaged* that nobody would think to look for;
* the storage vocabulary is translated exactly once, through
  `app/domain/vocabularies.py`, so `high` reaches the screen as `High` and
  `acknowledged` as `In Progress` --- the same words every other complaint
  surface sends;
* `POST /complaints/{id}/take-up` **declares no request body**, which is not a
  stylistic preference: the house `post()` helper on the frontend always sends
  `{}`, and a required model would turn every press of the button into a 422;
* every refusal comes out of the database. The 409 in particular carries the
  RPC's own sentence, naming whoever already holds the complaint, because
  "already taken up" with no name sends a supervisor to ask around an office.

*Total tests in this file: 14*

| Test Function | Description |
|---------------|-------------|
| `test_api_340_the_four_sections_arrive_grouped_as_the_database_grouped_them` | The frozen contract's load-bearing sentence: **bucketing is decided server-side**. Four rows go in, one per section, and each comes out in the section it went into --- nothing here re-derives *live* or *engaged*, which would be a second set of definitions free to disagree with the RPC's. |
| `test_api_341_the_stored_vocabulary_is_translated_exactly_once` | `high` reaches the screen as `High` and `acknowledged` as `In Progress`, through `app/domain/vocabularies.py` --- the same table every other complaint surface uses. The RPC deliberately sends the stored words: a `case` in SQL turning `high` into `High` would be a second copy of that table, in a language where nobody would look for it.  The **work order's** status is passed through unmapped, and that is not an inconsistency: `scheduled` is the work-order vocabulary, `WorkOrder` has always sent it, and a second spelling depending on which endpoint answered would be the real inconsistency. |
| `test_api_342_the_three_reassignment_badges_survive_the_projection` | `returnedToPoolAt`, `reopenedCount` and `reroutedAt` are the whole of section 1's "this is not as new as it looks", and `inheritedAt` is section 3's. All four ride on facts the engine already recorded --- none is a new lifecycle state --- so the only way to lose one is to drop it in the projection, which is exactly what nothing would error on. |
| `test_api_343_an_empty_department_is_four_empty_arrays_and_a_200` | Never a 404 and never a partial body. A department with nothing on it has four empty sections, which is a thing the screen can render; a missing key would be a section that throws. |
| `test_api_344_a_department_the_caller_does_not_supervise_is_a_403` | A refusal, not an empty snapshot.  An empty dashboard and a refused one look identical on a screen, and the difference is the whole content of the answer. The rule is `can_supervise_department` inside the RPC --- the same predicate `GET /departments/{id}/complaints` asks --- and nothing in Python restates it, because the copy that drifts is always the one nobody is testing. |
| `test_api_345_taking_up_needs_no_body_and_refuses_none` | **The route declares no request model at all**, and the frontend is why.  The house `post()` helper always sends `{}`, even for a body-less endpoint (`workerApi.acceptJob` is the precedent). A required model would answer 422 to every press of the button; a model with optional fields would be a place to name somebody else, and the acting supervisor is the session. Both an empty object and no body at all are a 200. |
| `test_api_346_somebody_else_s_complaint_is_a_409_that_names_them` | The refusal this verb exists to produce well. `take_up_complaint` raises `HB409` naming the holder, `pg_errors` passes a custom code's message through untouched, and it reaches the screen --- because "already taken up" without a name sends a supervisor to ask around an office. |
| `test_api_347_an_unknown_complaint_is_a_404_from_the_database` | Nothing in this process reads a complaint before writing to it. A lookup here would be a second answer to "does this exist", asked with the caller's RLS rather than the RPC's, and the two would disagree on exactly the rows that matter. |
| `test_api_348_taking_up_without_the_csrf_pair_is_refused` | It changes what a resident sees --- `open` becomes `acknowledged`, which their screen renders as *In Progress* --- so CSRF is checked before the role guard has anything to say. |
| `test_api_349_a_worker_membership_reaches_both_operations` | The claim the whole surface rests on. A department supervisor holds a `worker` membership --- rank is not role, `0035` settled that --- so the coarse router guard has to admit every worker, and what they may do to *this* department is `can_supervise_department` in Postgres. This proves the half that is Python: no route here refuses them before the database is asked. |
| `test_api_350_a_resident_reaches_neither` | The other half of the same table, and the reason the guard is there at all: it turns "signed-in resident poking at department ids" into a 403 before any query runs. The person whose flat the leak is in has their own screens and this is not one of them. |
| `test_api_351_an_admin_reaches_both_because_managing_implies_supervising` | `can_manage_department` implies `can_supervise_department` --- it is the first line of that predicate's body (`0036` 4) --- so an admin opening a department's dashboard is not a widening, it is the rule already written. Asserted because the router guard and the database predicate are two different lists and only one of them is in this repository's Python. |
| `test_api_352_a_malformed_section_empties_itself_and_not_the_screen` | The one piece of defensiveness in the service, and its bound.  `jsonb_agg` over an empty set is `null`, which the RPC already coalesces to `[]`. If a section ever arrives as something else, it renders empty rather than raising --- because one malformed section should not take the other three off the screen with it. This is a fallback and not a contract: the RPC owns the shape. |
| `test_api_379_the_sixth_section_carries_the_jobs_waiting_on_a_resident` | The 2026-08-23 ruling F1's dashboard half: a job the resident has been asked to put an hour on is not an *open request*. Nothing on it is the supervisor's to move -- they cannot pick the time and they are not meant to -- so listing it beside the work they can take up was showing them a queue that was not theirs.  `openRequests` narrows to `draft` and `offered` in the same change, and the split is the RPC's: this asserts only that the seventh key is read and rendered as its own array, because a service that dropped it would leave the new section permanently and silently empty. |


## `test_system.py`
System and authorization-boundary API cases.

*Total tests in this file: 2*

| Test Function | Description |
|---------------|-------------|
| `test_api_001_health_check_returns_environment` | No description provided. |
| `test_api_002_dashboard_snapshot_rejects_unauthenticated_request` | No description provided. |


## `test_work_orders.py`
Work orders, from the supervisor's side.

The plan's verification for this step is **"the overlap constraint rejects a
double-booking"**, and no in-process test can prove that: the constraint lives
in Postgres and these tests replace the repository. What they *can* prove is
everything around it -- that the API reaches the constraint rather than
routing around it, that the refusal it produces survives the translation layer
as a 409 with the RPC's own sentence, and that the state machine has no
transition reachable here that the RPC was not asked for.

Three assertions in this file are about **absence**, which is the harder kind to
notice going missing:

* ``PATCH /work-orders/{id}`` never forwards a status or a time. Both have their
  own routes because both carry a notification, and a general-purpose edit is
  exactly the shape that skips them.
* No route reads a caller-supplied id to decide who may act. Every 403 in this
  surface comes out of ``can_supervise_department`` in the database.
* Assigning forwards the job's own slot when the request omits one, rather than
  quietly writing a booking with no time -- which would be a booking the overlap
  constraint cannot see.

*Total tests in this file: 19*

| Test Function | Description |
|---------------|-------------|
| `test_api_160_triage_without_a_slot_is_a_request_not_an_omission` | The fork the whole feature turns on, and since the 2026-08-23 ruling F1 it is the only path the UI takes: the raise form carries no date or time for anyone, so both slot fields reach the RPC as `None` and `create_work_order` decides from the subject. A resident job becomes a request for the resident to name the hour; a facility job becomes a `draft` the queue books for itself. A request that silently substituted `now()` would propose a visit no human chose -- which is the whole defect the ruling removed.  **The field is still accepted** (adjudication G1). A slotted raise keeps today's semantics exactly, which is what the three tests below exercise; what changed is what a *slotless* one means. |
| `test_api_161_half_a_slot_is_refused_before_it_reaches_the_database` | `0036` signals a half-slot with `22004`, which `pg_errors` maps to a 422 carrying the repository's generic message -- true, and no help in naming which of two fields is missing. The model refuses it first so the caller is told, and the CHECK constraint stays the guarantee rather than the explanation. |
| `test_api_162_a_slot_that_ends_before_it_starts_is_refused` | The same reasoning one step further: a backwards range would build a `tstzrange` Postgres rejects outright, and the error that produces names the range rather than the field. |
| `test_api_163_the_department_and_skill_are_derived_when_omitted` | Both reach the RPC as `None` rather than being guessed here. The department comes from the complaint and the skill from its category, and both derivations live in SQL because that is where the rows are -- a Python lookup would be two more round trips and a second answer to a question `0034` already answered. |
| `test_api_164_an_unknown_subject_kind_is_named_rather_than_passed_through` | `subjectKind` decides whether anybody is asked to confirm the time, so a typo silently stored would be a resident never asked. The service checks it against the same two words `work_orders_subject_kind_check` allows. |
| `test_api_165_a_job_the_policy_hides_is_a_404_not_a_403` | `can_read_work_order` hides a job the caller has no part in rather than refusing it, so a stranger walking work-order ids learns nothing from which refusals come back. The read is a 404 for a job that does not exist and a 404 for one they may not see, and those are deliberately the same answer. |
| `test_api_166_the_detail_read_returns_the_whole_assignment_history` | Withdrawn and declined rows stay, because "we sent Ravi and he could not get in, so we sent Anil" is the question a supervisor actually asks. The *current* holder is the top-level `assigneeName`, which is a different field for a different question. |
| `test_api_167_the_patch_forwards_no_status_and_no_time` | The absence is the assertion. A status or a time arriving through a general-purpose edit would move the job without the notification and without the overlap check that `/assign` and `/reschedule` carry -- so the request model has no field for either, and unknown keys reach the repository as nothing at all. |
| `test_api_168_assigning_without_a_slot_forwards_the_job_s_own` | Both slot fields reach the RPC as `None`, which is what tells `0036` to use the job's own times. The alternative -- writing a booking with no time -- would be a booking the exclusion constraint cannot see, because it is partial on `scheduled_start_at is not null`. |
| `test_api_169_a_double_booking_is_a_409_carrying_the_rpc_s_own_sentence` | The refusal this step exists to produce. `0036` raises `HB409` naming the worker, `pg_errors` passes a custom code's message through to the caller, and the same 409 comes back if the constraint rather than the check catches it -- so a race and a mistake are indistinguishable to a client, which is correct. Nothing in Python decides this. |
| `test_api_170_the_403_comes_from_the_database_and_not_from_this_process` | The fixture's caller is an admin, so the router guard admits them; the department check is `can_supervise_department` inside every RPC. A copy of that rule here would be a second statement of it with nothing keeping the two in step, and the one that drifts is always the one nobody is testing. |
| `test_api_171_cancelling_without_a_reason_is_refused` | The reason reaches both the worker and the resident in a notification. A cancellation nobody can explain is the one that produces the phone call this feature exists to prevent, so it is required by the model as well as by the RPC. |
| `test_api_172_rescheduling_requires_both_ends` | Unlike creation, this is not a partial edit: there is no such thing as moving the start of a visit and leaving its end where it was, because the assignment's range moves with it and a range needs two ends. |
| `test_api_173_the_department_queue_forwards_its_status_filter_unwidened` | `?status=` narrows on top of the policy and never decides visibility. A supervisor asking for another department's queue gets an empty list from the policy rather than somebody else's work, which is why taking a department id from the path is safe here at all. |
| `test_api_174_a_complaint_may_carry_several_jobs` | A failed visit is rescheduled and a reopened complaint goes to a different supervisor, and both are a second work order rather than an edit to the first. This is the read that would have been impossible had the assignment been columns on `complaints` -- the smaller change the plan rejected in D5. |
| `test_api_175_an_unsafe_call_without_the_csrf_pair_is_refused` | Every write on this router changes somebody's working day, so CSRF is checked before the role guard has anything to say. |
| `test_api_337_a_worker_membership_reaches_every_work_order_operation` | The whole table, because a single call would leave eight untested and the one that drifts is always the one nobody looked at.  A supervisor is a `worker` and passes the coarse guard; what they may do to *this* department is `can_supervise_department` in Postgres, which is stubbed here -- so what this proves is the half that is Python: no route in this router refuses them before the database is asked. That is precisely the claim the worker portal's new `/worker/work-orders` route rests on. |
| `test_api_338_a_resident_reaches_none_of_them` | The other half of the same table, and the reason the guard is there at all: it turns "signed-in resident poking at work-order ids" into a 403 before any query runs. Widening the router to admit a supervisor did not widen it to admit the person whose flat the visit is in -- who has their own routes, in `resident_scheduling.py`. |
| `test_api_339_the_candidate_read_admits_the_supervisor_who_needs_it` | Named on its own because the screen leans on it harder than the others.  `GET /departments/{id}` is `require_admin_or_manager` and a supervisor cannot call it, so the roster the assign box offers does **not** come from the department read -- it comes from here, which admits them. If this route ever narrowed to match the departments router, the worker portal's assign box would go quietly empty rather than fail. |


## `test_worker_communities.py`
A service person finding work.

The same guard property ``test_service_providers.py`` pins, for the same reason:
the fixture overrides **only** identity and leaves ``get_active_membership``
live, so a membership guard creeping onto one of these routes runs the resolver
against the sentinel client and fails the test. This is the surface a provider
uses *because* nobody has hired them yet; requiring a membership here would make
the product un-hireable, and that failure would be invisible in a test that
stubbed the membership out.

Beyond the guard, three things are asserted that the migration alone cannot
promise: that both directions of a negotiation arrive in one list, that
withdrawing reaches the RPC as ``withdrawn`` rather than as a delete, and that
an unregistered caller is a 404 rather than an empty list.

*Total tests in this file: 13*

| Test Function | Description |
|---------------|-------------|
| `test_api_136_the_applications_list_carries_both_directions` | An application sent and an invitation received are one row shape with a different `direction`, and a client switches on it to decide whether to render 'withdraw' or 'accept / decline'. Two lists would make a provider check two screens to learn whether anyone wants them. |
| `test_api_137_an_unregistered_caller_is_a_404_not_an_empty_list` | "You have not registered" is a different answer from "nobody has hired you", and the dashboard routes on the difference -- one sends them to the registration form, the other to the community search. |
| `test_api_138_the_community_search_needs_no_registration_and_no_membership` | The search resolves the caller inside the RPC, so it neither 404s an unregistered caller nor 403s one who belongs to no community. An empty list is the honest answer to 'which communities need trades you have not told us about'. |
| `test_api_139_applying_reads_the_negotiation_back_rather_than_echoing_it` | The response carries the community name, the provider's skills and the distance -- none of which the request contained. Echoing the request back would return everything except what the screen renders. |
| `test_api_140_withdrawing_reaches_the_rpc_as_a_decision_not_a_delete` | `DELETE` is the verb the screen wants; `withdrawn` is what the database records. Nothing is removed -- the row stays on the list with a new status, which is why the route returns it rather than a 204. |
| `test_provider_can_accept_an_invitation_without_supplying_employment_terms` | No description provided. |
| `test_provider_invitation_decision_rejects_employment_terms` | No description provided. |
| `test_provider_invitation_decision_rejects_withdrawn` | No description provided. |
| `test_api_141_applying_without_the_csrf_pair_is_refused` | No membership guard on this router, so CSRF is the only thing standing between a cross-site form post and an application somebody did not make. |
| `test_api_213_the_roster_row_is_named_in_the_path_not_guessed` | A service person hired by three societies is leaving exactly one of them, and nothing in the session says which. Deriving the community from a default membership would resign them from whichever one sorted first. |
| `test_api_221_a_leave_date_is_forwarded_and_not_reinterpreted` | The worker's popup picks *immediately* or *a date*; immediately is spelled by omitting the field. The service forwards the date as an ISO instant and adds nothing — deciding what the date means (the freeze, the release window) is `0045`'s job, in one place, in SQL. |
| `test_api_214_each_community_card_carries_its_own_open_request` | One read, not one per card. The leave button on a community card says 'request' or 'withdraw' depending on this field, and a provider on four rosters would otherwise cost four round trips to render one screen. |
| `test_api_215_withdrawing_a_request_that_is_not_open_is_a_404` | A 200 here would tell a provider their request was withdrawn when the manager had already approved it — and the next screen they see is the one that no longer lists the community. |


## `test_worker_jobs.py`
The worker portal's job surface.

Same guard property as ``test_worker_communities.py``, and here it is the
property most worth pinning: the fixture overrides **only** identity and leaves
``get_active_membership`` live, so a membership guard creeping onto one of these
routes runs the resolver against the sentinel client and fails. A guard on this
surface would read the role off whichever community happens to be the caller's
default, and a plumber who lives in one society and works in three others would
lose their own job list to it -- silently, and only for the people it matters
most for. See ``docs/plans/SERVICE_OPERATIONS_PROGRESS.md`` 4.16.

Beyond that, four things the migration alone cannot promise: that the list and
the detail carry different fields on purpose, that every verb answers with the
row the database settled on rather than the request, that an unregistered caller
gets a snapshot rather than an error, and that the notification badge is counted
across every community the caller works in.

*Total tests in this file: 11*

| Test Function | Description |
|---------------|-------------|
| `test_api_185_the_list_filters_on_two_different_states` | `assignmentStatus` asks what is being asked of me and `status` asks what is happening to the job. A withdrawn assignment on a job that went ahead without you is visible under the first and invisible under the second, and collapsing them into one filter loses the question a worker is actually asking. |
| `test_api_186_the_list_withholds_what_only_the_detail_needs` | The resident's name, flat and number are on the job a worker is on their way to and not on a month of finished ones. The split is in the select list, so this asserts the response shape rather than the query. |
| `test_api_187_accepting_answers_with_the_row_the_database_settled_on` | The whole point of accepting is the status afterwards, and only the re-read knows it: the request carried no status and the RPC returns an id. Echoing the request back would show `offered` on a job that is now `scheduled`. |
| `test_api_188_somebody_elses_job_is_a_404_and_not_a_403` | The view returns nothing for a job the caller holds no assignment on, and a 403 would confirm that the id exists. Every route on this surface answers the same way for the same reason. |
| `test_api_189_a_failed_visit_must_say_why_and_a_declined_offer_need_not` | The asymmetry is deliberate. A worker who was asked and is not free owes nobody an explanation; a worker who went and could not do the work is reporting something the next person has to act on, and "could not be done" with nothing after it guarantees a second wasted visit. |
| `test_api_190_an_unregistered_caller_gets_a_snapshot_not_a_404` | This endpoint is the empty state. A null `provider` means "show the registration form" and an empty `communities` means "show the community search" -- both answered by one response rather than by a client interpreting two failures. `GET /service-providers/me` still 404s, because there the question is different. |
| `test_an_invited_supervisor_gets_their_engagement_with_no_provider_row` | The defect live testing found. `claim_staff_invitations` writes a membership and a roster row and no `service_providers` row, so an invited supervisor is *unregistered* by every provider-keyed read -- and the snapshot used to return on the spot, empty. The portal read that as "show the marketplace registration form" and the Complaints screen, which decides supervisor access from `communities[].rank`, had nothing to decide from.  `provider: null` and a populated `communities` are now an ordinary answer: the two questions -- *do you have a marketplace profile* and *does anybody employ you* -- are asked separately because for leadership they have different answers. |
| `test_api_370_the_board_names_the_roster_row_and_keeps_the_null_slot` | Two promises the frozen interface makes. `staffAssignmentId` is the caller's own roster row, returned so the frontend never guesses which of a multi-community worker's rows a claim rides on. And a null slot passes through as null rather than being dropped or defaulted -- ruling C3 says an unscheduled job is on the board with a "time to be set" marker, and the marker is the client's to draw from exactly this null. |
| `test_api_371_claiming_answers_with_the_row_the_database_settled_on` | The same contract as accepting, and it matters more here: the claim is the race the board creates on purpose, and only the re-read knows the job the caller now holds is `scheduled` -- possibly with no slot yet, which is C3's shape rather than an error. |
| `test_api_372_losing_the_claim_race_is_a_409_in_the_servers_words` | First come, first served (C2) means somebody loses, ordinarily. The RPC locks the work order before it reads anything, so the loser is told *somebody has already taken this job* -- a sentence the card can print -- rather than shown an exclusion-constraint violation. |
| `test_api_191_the_badge_counts_every_community_the_caller_works_in` | The one place a user can see the multi-membership seam. A count scoped to a default community would silently drop the notifications from the two societies a plumber is not currently 'in'.  Since `0041` the count is asked of the *person*, which is what makes that true for a provider whose engagements are still being decided -- a badge assembled from a list of memberships is empty for somebody who holds none, and an unhired provider with an unanswered application is exactly who has something waiting. |


## `test_worker_schedule.py`
The worker's calendar, their leave, and the week they will work.

Three properties here are decisions rather than plumbing, and each would survive
a refactor that broke it: the calendar is one list of two kinds, its range filter
matches on **overlap** rather than on start, and the working week is replaced
whole rather than edited.

The overlap one is the least obvious and the most load-bearing. A fortnight of
leave that a one-week calendar sits in the middle of starts before the window and
ends after it, so a filter on ``starts_at`` alone would drop exactly the block
that matters most -- and the worker would be shown as free on a week they had
booked off.

*Total tests in this file: 6*

| Test Function | Description |
|---------------|-------------|
| `test_api_192_the_calendar_is_one_list_of_two_kinds_in_time_order` | A calendar that returned jobs and made the client fetch leave separately would draw a worker as free on a day they had booked off, for as long as the second request took to arrive. |
| `test_api_193_the_calendar_omits_what_is_not_a_claim_about_the_future` | A declined offer and a cancelled job are both history. A calendar is a claim about where somebody will be, and neither of those is one. |
| `test_api_194_the_leave_filter_matches_on_overlap_not_on_start` | The block that matters most to a week is the fortnight it sits inside, which starts before the window opens. Filtering `starts_at` against both bounds would drop precisely that one. |
| `test_api_195_removing_a_block_answers_204_with_no_body` | Unlike a withdrawn application, a block that is gone leaves nothing on the screen it came from, so there is no row to return. |
| `test_api_196_the_working_week_is_replaced_whole_in_the_rpcs_vocabulary` | The RPC reads its jsonb with `rule->>'startTime'`, so the service has to send camelCase into the database even though every other repository argument is snake_case. Getting this wrong casts null to time and fails at the insert, a long way from the endpoint. |
| `test_api_197_a_backwards_window_is_refused_before_the_database_sees_it` | The CHECK constraint is the guarantee; this is the sentence. A 422 naming the field beats a 422 carrying the repository's generic message, which is what the constraint's own 23514 would arrive as. |


