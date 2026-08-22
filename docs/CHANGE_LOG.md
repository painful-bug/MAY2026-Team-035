# Design change log

Every change made to the design artifacts in `docs/`, with the reason for it.

This file exists because the backend design is being derived from a frontend prototype, a class
diagram, an ERD and a component design that were written independently and disagree with each other
in places. When one of them changes, the *reason* is the part that is expensive to reconstruct later
— six weeks from now "why is `department_kind` not a list of trades?" is a much harder question than
"what is `department_kind`?". So the reason is recorded here, next to the change, at the time.

**Scope.** Design artifacts under `docs/` only. Application code has its own history in git.

**Convention for new entries.** Newest session first. Within a session, group by artifact. Each entry
names *what* changed, *why*, and *who decided* — `PO` for a product-owner ruling, `DERIVED` for a
consequence of one, `AUDIT` for something found by comparing artifacts against each other. A ruling
that overturns something already written says so explicitly, including what it overturned.

---

## 2026-08-22 (latest) — nobody could raise a work order, and the supervisor gets a real dashboard

**`docs/plans/MIGRATION_APPLY_RUNBOOK.md` §17 + `backend/supabase/migrations/20260822090000_hosted_work_order_column_drift.sql`.**
`AUDIT` (live testing, 2026-08-22). The supervisor's "Raise it" button answered
422 "Could not raise that job." — as would the admin's, for every caller. Traced
to hosted schema drift, not to any code: the hosted `work_orders` table is the
pre-baseline hand-built one, and a legacy `title` column (NOT NULL, no default,
declared by no repository migration) rejected every `create_work_order` insert.
Same disease `20260820120000` reconciled on `complaints`; same cure — a
hand-applied widening sweep that drops the insert-blocking legacy NOT NULLs,
self-verifies, and is pinned by
`backend/tests/test_hosted_work_order_drift_migration.py` (protected column
list *derived* from `0001`+`0036`+`20260813101000`'s own text, so a repository
column can never be loosened by mistake). Diagnosis was only possible after
`app/core/pg_errors.py` started logging the real Postgres text server-side for
mapped standard SQLSTATEs — that log line stays.

**`docs/COMPLAINT_ENGINE_HANDOFF.md` §18.** `PO` (2026-08-22). The supervisor's
landing surface is redesigned into four sections — new (urgent stack, category
and priority chips, reassigned badges), taken-up-but-unassigned,
assigned-but-pending, being-worked-now. Four rulings recorded for the
complaint-engine owner: an explicit *Take up* action stamps
`taken_up_by_membership_id`/`taken_up_at` (triage ownership, **not** dispatch —
§15 ruling 1's dead column stays dead); take-up moves `open → acknowledged`, so
the resident sees progress; §16's "no new column" for re-stamping is partially
overturned by `supervision_inherited_at`, so inherited work can be badged on a
supervisor-only surface; and "being worked right now" is the worker's own
Start (`started_at` stamp added, *Pause* deferred rather than rippling a new
status through the dispatch triggers). One aggregate read
(`supervisor_triage_snapshot`) replaces the triage screen's N+1.

**Same day, the build landed** (`DERIVED` from the §18 rulings; two specialist
agents against the frozen contract in `docs/plans/SUPERVISOR_TRIAGE_SPEC.md`,
whose "Logged decisions" section records every reconciled judgement call).
`docs/API.md` gains "The supervisor's dashboard — added 2026-08-22":
`GET /departments/{id}/triage-snapshot` and `POST /complaints/{id}/take-up`
(55 → 57 operations; take-up declares no request body because the frontend's
house `post()` always sends `{}`); `docs/openapi.yaml` regenerated (172 paths,
203 operations) and `docs/api_yaml_mapper.md` re-run. The runbook gains §18
for `20260822120000_supervisor_triage.sql` — take-up columns, `started_at`,
`supervision_inherited_at`, both RPCs, additive-copy redeclarations of
`start_work_order` and `restamp_department_supervision` proved line-by-line by
`test_supervisor_triage_migration.py`. `docs/FRONTEND_CHANGES.md` gains "The
supervisor lands on their department, not on an empty calendar": the `/worker`
index forks on roster rank, phase one ships the shell plus Section 1 complete
(urgent stack, category palette that excludes the priority tones, reassignment
badges, Take-up), sections 2–4 await product review. Test baselines:
backend 1163 → 1205 passed / 4 skipped, frontend 34/182 → 36/215, both green.

**Runbook §19 + `backend/supabase/migrations/20260822150000_taken_up_event_word.sql`.**
`AUDIT` (live testing, 2026-08-22, same day). The very first live Take-up
press answered 422 "Could not take that complaint up." — SQLSTATE 23514,
`complaint_events_type_check`. The triage migration reasoned from `0001`'s
"event_type is text with no CHECK" and missed that `20260813105000` had
bolted an enumerating constraint on later; its new `taken_up` timeline word
was refused at the insert. Cure: recreate the constraint with the one new
word, in the creating file's own drop-and-recreate shape. Pinned by
`backend/tests/test_taken_up_event_word_migration.py` (word list *derived*
from `20260813105000`'s own text plus exactly `taken_up`; also proves the
triage migration writes no other unknown word, so the cure has no hidden
sibling). Backend baseline 1205 → 1211 passed / 4 skipped. Second find of the
day for the `pg_errors` server-side log line — the 23514 was named in one
log read.

**`docs/plans/SUPERVISOR_TRIAGE_SPEC.md` Amendment 2 + `docs/COMPLAINT_ENGINE_HANDOFF.md` §20.**
`PO` (2026-08-22, same day). The dashboard grows from a place to look into a
place to act: five sections (an *Open job requests* section slots between
taken-up and assigned), three universal card actions (eye popup with the full
staff timeline, chat with the complaint owner, permanent internal note), and
stage verbs — raise-job deep-link and *Resolved* on §2; mark-resolved,
one-way priority raise and manual assign on §3; §4/§5 monitor-only. Four
explicit rulings: chat is a **real thread** (new `dm_threads` kind, not a
comments panel); *Resolved* cancels unstarted jobs and refuses while one is
running; a job is *open* until a worker **accepts** (an unaccepted offer is
not "assigned", overturning v1's `engaged` definition); manual assign is a
**true force-assign** — the product owner chose the consent override over the
recommended offer flow. Orchestrator riders: notes are internal-only (the
ruling's phrasing named staff and workers, not the resident), and raise-job
reuses the queue's form by deep-link rather than duplicating it. Three
resident-facing strings approved verbatim.

**Same day, the amendment-2 build landed** (`DERIVED`; same two-specialist
shape, adjudications appended to the spec's decisions log).
`backend/supabase/migrations/20260822170000_supervisor_actions.sql` carries
the whole DDL surface: complaint chat threads (kind + column + policies +
reopen-aware lock), the four action RPCs, an explicit
`force_assign_work_order`, the five-bucket snapshot rebuild, and the one new
event word `priority_changed` shipped **inside a constraint rebuild** —
runbook §19's rule applied in advance rather than after a live 23514.
Notable adjudicated deviation: `supervisor_resolve_complaint` writes no
`status_changed` and sends no notification itself, because the
`complaints_on_resolved` trigger already does both and arms the 48h/72h
timers — the migration refuses to apply if that trigger is absent.
`docs/API.md` gains "The supervisor's card actions — amendment 2" (resolve,
priority-raise, notes, chat, the `force` flag, and the staff-detail guard
widened from `require_admin` to active membership — the RPC underneath always
decided admin-or-supervisor for itself); `docs/openapi.yaml` regenerated
(`--check` clean), mapper re-run, runbook §20 appended.
`docs/FRONTEND_CHANGES.md` gains "The supervisor dashboard becomes a place to
act, not only to look" — full cards everywhere, `MinimalRow` retired, the
deferred *Inherited* badge shipped, `ChatDock` learns to open a thread by id.
Test baselines: backend 1211 → 1270 passed / 4 skipped, frontend
36/215 → 38/264, oxlint clean — re-run by the orchestrator, not taken from
agent reports. Migration awaiting the owner's hand-apply.

## 2026-08-22 — the admin Save button was accused of writing nothing; it writes everything

`AUDIT` (orchestrator verification, 2026-08-22). A specialist report from the
2026-08-21 deep-link workstream flagged, out of scope, that
`AdminDashboard/Complaints.jsx`'s *Save Changes* and comment controls "write to
zustand only — no server call". Line-verified false before any fix was planned:
`store/slices/createComplaintsSlice.js` follows its optimistic store write with
`PATCH /complaints/{id}` and `POST /complaints/{id}/comments`, both routes exist
in `backend/app/api/v1/routers/complaints.py` behind `require_admin`, the edit
and its timeline entries are one transaction, and both writes fire the shared
SSE trigger that re-snapshots the dashboard. The rumour never reached a docs
artifact, so nothing is retracted — this entry exists so the claim is findable
next to its refutation.

**What the audit did expose, and what changed.** A *failed* write fires no SSE
event, so the optimistic copy of the refused state sat on the card indefinitely
with only a transient toast against it. The slice's catch now re-reads the
snapshot for server truth, falling back to restoring the affected row locally
when the snapshot read fails too. Application-code change; recorded in
`FRONTEND_CHANGES.md` ("A refused complaint write no longer stays on screen")
and, because the surface belongs to the complaint-engine owner, in
`COMPLAINT_ENGINE_HANDOFF.md` §17 — which also notes for the owner that the
screen's "Staff / Assignee" box persists a display label (`assignee_label`),
not an assignment: it does not touch `assigned_to_membership_id` and drives no
dispatch, consistent with §15's ruling 1 (complaints stay department-pooled).

## 2026-08-21 — a supervisor's removal stops breaking the complaint chain

`PO` (product owner, 2026-08-21). Seven rulings in one sitting, all about what
happens to a department's work when the person supervising it leaves. They are
recorded in full in `COMPLAINT_ENGINE_HANDOFF.md` §15; what follows is what
changed in `docs/` because of them.

**Ruling 1 — complaints stay department-pooled.** This closes the question §14 of
the handoff left open. `complaints.assigned_to_membership_id` remains a dead
column: one function writes it (`update_complaint`, `0031`), nothing reads it, and
nothing new does either. A complaint belongs to a department, and the person who
answers it is named on the *work order*, which is a different record with a
different lifetime.

**Ruling 2 — removal continuity is work-order re-stamping.** The defect the
sitting revealed: `work_orders.supervisor_membership_id` is the delivery address
for five notification kinds (`work_order.no_candidates`,
`work_order.resident_accepted`/`_declined`, `work_order.accepted`,
`work_order.completed`, `work_order.failed`) and nothing anywhere re-pointed it
when the person it named left. `20260821140000` §8 then made those rows invisible
to their recipient as well, so a department's live jobs reported their progress
into a mailbox nobody could open. Live work orders now move to the least-loaded
remaining active supervisor of the same department, else to its manager, else
nowhere — *a wrong address is worse than a stale one*.

**Ruling 3 — the last supervisor's departure is a notification and a banner, not
a new screen.** The manager is told they are covering the queue, and their
Complaints screen says so while it is true. Explicitly **not** a new workspace:
`can_manage_department` implies `can_supervise_department` (`0036`), so the
manager's screens already exceed the supervisor's, and building a second one would
be building a subset.

**Ruling 4 — removal gets a real confirmation dialog.** The two `window.prompt`
flows on the roster tab asked for a reason and, by being the only thing in the
way, doubled as the confirmation. Now a sheet that names the person, states what
they actually hold, and warns when they are the last supervisor.

**Ruling 5 — the always-zero roster count dies.** `activeAssignmentCount` counted
open complaints by `assigned_to_membership_id` or by a prefix match on
`assignee_label`: one column nothing writes and one no frontend has ever set. It
was `0` on every row of every roster ever rendered, displayed as "0 open
complaints" beside a real number. Replaced by `supervisedWorkOrderCount`, which
somebody writes.

**Ruling 6 — the admin "Assign to staff" control is removed.** This executes R13,
which the change log recorded as settled on 2026-08-13 and which was never done.
The control wrote `assigneeStaffId` into zustand and nowhere else.

**Ruling 7 — supervisors really are notified when a complaint is raised.** This
executes R18, recorded as done and never implemented: `notify_complaint_staff`
reached admins and the department's manager and stopped. A supervisor is a *rank
on a roster row*, so no role-based helper could name them, which is how the gap
survived a review that read the audience as "admins and managers" and found it
correct.

**Ruling 8 — the claim pass runs on every session read.**
`auth_service._claim_staff_invitations` was called only on the branch that had
already established the caller holds no membership, so anybody who already
belonged to a community never reached it: their pending leadership invitation was
neither applied nor refused, and the inviting department went on seeing `pending`
forever with nothing reporting a problem. The refusal half added by
`20260821140000`/`20260821170000` was reachable by the same narrow population
only.

**Ruling 9 — the serviceman release mechanics are untouched.** The rank-1 "just
below urgent" re-queue in `release_staff_commitments` already does what the owner
wants. Recorded so nobody re-opens it.

**Migration — `20260821200000_departure_continuity.sql`. NOT APPLIED. The
repository owner must paste it into the Supabase SQL editor by hand.** Three new
helper functions, one new trigger function and its trigger on `staff_assignments`,
a redeclared `notify_complaint_staff` (ruling 7), a recreated
`department_staff_overview` (ruling 5), and a `do` block that repairs work orders
already addressed to an ended membership and reports the count. It adds no column,
no table, no policy and no SQLSTATE, and it deliberately declares no
`claim_staff_invitations` — ruling 8's fix is a Python call site, and a
redeclaration here would have to guess which generation of that body
(`20260821140000`'s or `20260821170000`'s) is on the database.

**A trigger, not an edit to `remove_department_member`, and that is the entry
worth keeping.** Removal has four RPC entry paths and a fifth that is not an RPC:
`staff_assignments_admin_write` is `for all to authenticated` with direct grants
(`20260812200000`), so an admin can flip `status = 'inactive'` straight through
PostgREST. All five end at the same `update public.staff_assignments`, so one
`after update` trigger covers five where a function edit covers four —
`20260821140000` §2 chose triggers over RPC edits for the same reason, and this is
that argument applied to continuity rather than to an invariant. `after` and not
`before`, so the departing row is already `inactive` in the snapshot the successor
search reads and "a remaining active supervisor" excludes them by construction.

Artifacts changed:

* `API.md` — §3.5 records that the claim pass now runs on every session read and
  what the old guard cost; §7's audience note gains the department's supervisors
  and the R18 history; §8's `StaffMember` prose replaces `activeAssignmentCount`
  with `supervisedWorkOrderCount` (and says the old field is *gone*, not renamed,
  so a client reading it gets `undefined` rather than a wrong number); the sample
  payload follows; `POST …/members/{staffId}/remove` gains the re-stamping
  contract, the `department.supervision_uncovered` notification, and the statement
  that residents and workers see nothing — by construction, not by suppression.
* `plans/MIGRATION_APPLY_RUNBOOK.md` — §16 for the new file, in §13–§15's style,
  paste-and-run verification only. **Two stale-header repairs in the same edit**:
  the title said "the seven unapplied migrations" and §0.2 said "confirm the
  highest version present is `0047`", both fifteen migrations out of date — §0.2
  would now stop the owner on a database that is exactly where it should be. A
  dated box under the title gives the real state, and §0.2 keeps its original text
  labelled as the §1–§7 boundary with the modern check beside it. §15's
  "and is the last file in the directory" row is corrected to the property it was
  standing in for.
* `COMPLAINT_ENGINE_HANDOFF.md` — §15, all nine rulings with attribution and date.
  It answers §14's open question about the pooled model rather than leaving it
  open beside a decision that assumes an answer.
* `FRONTEND_CHANGES.md` — the dialog, the banner and the removed control.
* `openapi.yaml` — `DERIVED`. `python scripts/export_openapi.py`;
  `--check` reports it up to date. `StaffMember` and `StaffMemberDetail` swap
  `activeAssignmentCount` for `supervisedWorkOrderCount`; no path, request or
  status code moves.
* `api_yaml_mapper.md` — `DERIVED`. `python scripts/regen_mapper.py` reports it up
  to date: the mapper keys on endpoints, and no endpoint changed.
* No ERD or class-diagram change: no column is added, removed or re-typed. The
  re-stamp writes `work_orders.supervisor_membership_id`, which both diagrams
  already carry, and the meaning of the column is unchanged — only the number of
  things that maintain it.

---

## 2026-08-21 — the supervisor gets the screen they were already allowed to use

`PO` (product owner, 2026-08-21): **"The supervisor is the channel through whom
the worker gets the job."** Mount the existing work-order triage screens in the
worker portal for supervisor rank.

**What the ruling found.** A service department's supervisor holds a `worker`
membership — rank is not role, `0035` settled that — so `_portal_for` lands them
in `/worker`. `WORK_ORDER_ROUTES` in `App.jsx` was mounted under
`/security-manager`, `/manager` and `/admin`, and under `/worker` there was no
work-order screen at all: the person whose job is dispatch had one complaint
list with one button. The comment above the `/security-manager` mount had
already written the argument against this — *"`can_supervise_department` is what
every work-order RPC checks, and a supervisor satisfies it, so this surface is
theirs to use rather than merely to look at"* — for a portal a supervisor of a
plumbing department never sees. The ruling resolves the contradiction the way
that comment wanted.

**`DERIVED` — no permission moved, and none needed to.** The nine endpoints in
`work_orders.py` are guarded `require_membership_role("admin","manager","worker",
"security")` at the router and `can_supervise_department` inside every RPC
(`0036:435`), which admits a `manager`- or `supervisor`-rank roster row. What was
missing was a route. `backend/tests/api/test_work_orders.py` now sends all nine
as a `worker` membership (`test_api_337`) and all nine as a resident
(`test_api_338`), so the claim this mount rests on is a test rather than an
assumption.

**`AUDIT` — one read genuinely refuses a supervisor, and it is not a
work-order route.** `GET /departments/{id}` is `require_admin_or_manager`
(`departments.py:47`), and the triage screen uses it for the department's trade
list and roster. The roster has a second source that does admit them
(`GET /work-orders/{id}/candidates`); the trade list does not, so on that read's
403 the screen now says which box is affected instead of rendering the guard's
own *"You do not have permission for this community action."* under the queue.
Widening that endpoint is a departments-owner decision and is **not** taken
here: it would expose every department's roster in the community to every
worker in it, which is a bigger question than a trade dropdown.

### Artifacts

* `FRONTEND_CHANGES.md` — the two routes, the rank-gated nav entry, the shared
  `supervisedEngagement`, and the department-read note. Appended to the *Worker
  portal* section.
* `backend/tests/api/README.md`, `backend/tests/README.md` — `DERIVED`,
  regenerated by `pytest --collect-only --generate-test-docs`.
* No `API.md`, `openapi.yaml` or `api_yaml_mapper.md` change: **no endpoint, no
  request and no response shape moved.** `GET /worker/snapshot` already carries
  `communities[].rank`, `.status` and `.departmentId` (`ServiceEngagement`,
  `hiring_schemas.py:314`), which is everything the new screen needed to know —
  so the snapshot schema was read, not extended.
* No ERD or class-diagram change: no table, column or relationship is involved.
* **Not fixed here, on record instead:** `portalNotificationUrl`
  (`frontend/src/features/notifications/portalUrl.js`) rewrites `/admin/…`
  notification urls for `manager` and `security-manager` only. A supervisor's
  portal is `worker`, so `20260812120000`'s seven work-order notifications still
  reach them spelled `/admin/departments/{id}/work-orders?job=…` and bounce off
  `ProtectedRoute requiredRole="Admin"`. The destination now exists, which is
  the half that was missing; the rewrite rule is per-portal and cannot simply
  gain a `worker` key, because that key would also rewrite `hiring`, `staff/`
  and `candidates/` — three sub-screens the worker portal does not have — and
  `backend/tests/test_notification_links.py` mirrors that rule table in Python
  and would have to grow a worker parametrisation with it.

---

## 2026-08-21 — the person whose invitation was refused is told why

`PO` (product owner, 2026-08-21, on reading the entry below): **the invitee must
be told why the invitation did not take.** The claim-time refusal shipped that
morning tells the department three times — `blockedReason`, `blockedAt`, and a
`staff_invitation.blocked` notification — and tells the person nothing at all.
They sign in with the address a manager typed for them, the invitation silently
does not take, they land in whatever portal their own identity already entitled
them to, and no surface in the product connects the two. Somebody told they had
been made a supervisor, who then signs in and finds an ordinary account, has been
handed a puzzle where an answer was owed.

The wording is the ruling and is frozen — approved verbatim, with the community's
name substituted:

> **Registered provider.** "Your invitation to join *{community}* couldn't be
> applied. This account is registered as a marketplace service professional, and
> department leadership can't be combined with a provider profile. Ask the
> community to invite a different email address."
>
> **Already leads elsewhere.** "Your invitation to join *{community}* couldn't be
> applied because you already manage or supervise another community. Leadership
> is held in one community at a time — once your current engagement ends, the
> invitation can be applied on your next sign-in."

`DERIVED`: **the same edge, not a second one.** The message is written inside the
existing `if v_row.blocked_at is null then` guard, beside the department's. The
claim runs on *every* membership-less session read and a blocked person keeps
signing in, so a message outside that guard is a message re-sent forever; and two
separate guards are two things that can drift into disagreeing about whether a
refusal has already been announced.

`DERIVED`: **`notify_profile`, so the row is person-scoped and community-less.**
It is `0041` §2's writer, built for exactly this population. Both refused people
are people a community-scoped row cannot serve: the registered provider holds no
membership anywhere, and the sitting leader's only membership is in the *other*
community — the one that caused the refusal — so the entry below's own ruling-3
feed scoping would hide the explanation on the day that posting ended. A
community-less row is what `membership_is_live(null)` deliberately keeps readable
forever.

`DERIVED`: **a separate `kind`, `staff_invitation.not_applied`.** Dotted, in the
`staff_invitation.` namespace the department's `staff_invitation.blocked` opened,
because these are one event told to two audiences. *Separate* rather than a second
row of the same kind because the two carry opposite voices — "they could not be
admitted" against "your invitation couldn't be applied" — and one kind that
renders as either sentence is one kind whose fallback title is wrong for half its
readers. The payload mirrors the department side's shape and names the community
where that one names the department.

`DERIVED`: **no `url`, and that is the house rule rather than an omission.** There
is no screen for this — the invitee is not a member of that community and never
becomes one, no portal lists invitations addressed to you, and the two refused
populations land in different portals. `notifications_service._FALLBACK_URLS`
already settled the general question: "a guess about where a notification should
land is a worse failure than no link, because a link that goes to the wrong screen
is one the reader believes." `render` returns `""`, and `NotificationBell` marks
the row read and navigates nowhere.

`AUDIT`, stated rather than fixed: **an invitation blocked before this migration
is applied is never told retroactively.** Its `blocked_at` has already crossed the
edge. Sending for those rows would mean writing `blocked_at` backwards or
bypassing the guard, and either would re-notify anybody the department has since
re-invited — so the migration counts them into a `raise notice` and touches
nothing, which is the entry below's §9 argument at a smaller scale. The
department's existing remedy already re-arms the edge: `update_staff_invitation`
clears `blocked_reason`/`blocked_at`, so a corrected or re-issued address
announces itself normally on the next sign-in. Expected count on the hosted
database: zero — the columns were added the same day.

**Migration — `20260821170000_blocked_invitee_notice.sql`. NOT APPLIED. The
repository owner must paste it into the Supabase SQL editor by hand.** It
redeclares exactly one function, `claim_staff_invitations`, under the house
convention for changing a function another migration owns (`20260812113000` §1):
the body is copied whole out of `20260821140000` §5 and every added region is
marked `-- CHANGED (20260821170000)`. No column, no table, no policy, no trigger,
no grant. It **must** sort after `20260821140000` and does.
`backend/tests/test_blocked_invitee_notice_migration.py` pins it statically: that
it parses, that it sorts last, that the copy is *purely additive* (every non-blank
line of the applied version is still present), that the loop still contains no
`raise`, that both notifications sit inside one edge guard, that both approved
sentences are stored character for character, and that nothing is destructive.

**One existing test was rewritten rather than deleted, and the precedent for that
is in this file.** `test_leadership_exclusivity_migration.py::
test_nothing_later_redeclares_what_this_file_owns` asserted that no later file may
declare any of nine names — stricter than the property that matters, and the same
assertion `test_location_label_migration.py` had already had to loosen a few hours
earlier when the leadership work copied `register_service_provider` forward. It
now exempts `claim_staff_invitations` **conditionally**: a later declaration is a
clash unless it carries every claim-time semantic forward — the skip, `pending`
status, both blocked columns, the edge guard and the department's notification.
The other eight names remain nobody's to redeclare.

Artifacts changed:

* `API.md` — §3.5's "a refused claim is invisible on this endpoint" paragraph is
  corrected to "invisible in this *response*" and gains the two-audience table,
  the frozen wording, and why the row is person-scoped and link-less; §8's
  leadership block records both notifications and why the invitee's copy is not
  the department's sentence; the `GET …/staff-invitations` note that
  `blockedReason` is "the only place that answer appears" is corrected to "the
  only place *this reader* gets that answer".
* `plans/MIGRATION_APPLY_RUNBOOK.md` — §15 for the new file, in the style of §13
  and §14, with paste-and-run verification only (§14's `PUT-A-ROSTER-ROW-ID`
  placeholder is the lesson: every check here self-selects its data or skips with
  a `notice`) and the ledger insert.
* `openapi.yaml` — **unchanged**, and verified rather than assumed: no endpoint,
  request, response or status code moves, and `python scripts/export_openapi.py
  --check` reports it up to date.
* `api_yaml_mapper.md` — `DERIVED`. `python scripts/regen_mapper.py`. 100 rows
  differ and **every one of them differs only in its `API.md:` line number**,
  which moved because §3.5 grew above them; normalising the line references makes
  the two files byte-identical. This is the drift the script exists to catch and
  the same regeneration the entry below needed.
* No `FRONTEND_CHANGES.md` bullet — no frontend file is touched.

Five-gate check: **No ERD change** — no column, no table, no relationship; one
function body moves. **No class-diagram change** — no entity, no attribute. **No
component-design change**: the feed renders `title`/`body`/`url` generically, and
a kind no JavaScript has heard of already renders from its own payload (pinned by
`test_api_284`). **Frontend**: nothing touched — verified rather than assumed;
`NotificationBell` reads `item.title`/`item.body` as text nodes and guards its
navigation with `if (item.url)`, so a link-less row of an unknown kind renders and
clicks correctly today. **Supabase**: the migration above, and it is the only DDL.

---

## 2026-08-21 — leadership is invite-only, exclusive, and revocable

`PO` (product owner, 2026-08-21) — three rulings, quoted rather than paraphrased
because all three are about who may see what:

1. **Leadership is invite-only and never from the marketplace pool.** "A
   supervisor or manager is NEVER a freelancer and is never picked from
   servicemen." A profile holding a `service_providers` row must never hold a
   `manager` or `supervisor` roster row, and a profile holding an active
   leadership membership must be refused marketplace registration.
2. **Leadership is exclusive to one community.** At most one active leadership
   membership per person across all communities, ever. Technicians may serve
   several communities and that is untouched. Being invited to a different
   community *after* the previous engagement has fully ended is legitimate and
   must keep working.
3. **Removal severs access completely.** Once a supervisor or manager is removed
   from a community and later invited to another, "they must not be able to see
   ANYTHING from the old community — engagements, complaints,
   conversations/messages, calendar, notifications, anything their portal reads."

`DERIVED`: **the invariants are triggers, not checks in each writer.** There are
five writers of `community_memberships` and four of `staff_assignments`, and a
guard repeated nine times is a guard that will be eight places the tenth writer
does not know about — `20260812113000` made the same argument for the
separate-account rule and it holds here. `staff_assignments` also carries
`staff_assignments_admin_write` (`20260812200000`), a `for all` policy that lets
any community admin insert a roster row straight through PostgREST with no RPC in
the way; nothing but a trigger stands in front of that. The RPCs additionally
refuse early, not for safety but for the *sentence*: a trigger fires three frames
below a registration form and the message that form renders should say what to do
about it.

`DERIVED`: **two new SQLSTATEs, not one.** `HBMKT` (ruling 1) and `HBLED` (ruling
2) are both 409s, like `HB409` and `HBSEP`, because all four answer *this account
is the wrong kind of account*. They are separate codes because a client that must
offer "hire them at technician rank instead" for one and "wait until they leave
the other society" for the other cannot tell them apart from an HTTP status, and
branching on message text is what custom SQLSTATEs exist to avoid.

`PO`-shaped judgement call, recorded because the charter asked for it:
**the claim-time refusal is a skip, not a raise.** `claim_staff_invitations` runs
inside `GET /auth/session`, on the service client, on every membership-less
session read, and `auth_service._claim_staff_invitations` swallows whatever it
raises — deliberately, because claiming is an enhancement to a session that is
already valid. A refusal spelled as an exception would therefore not refuse *that*
invitation; it would abandon the whole call, including any legitimate invitation
later in the same loop, silently, behind a screen that looks fine. So the
offending invitation is **skipped and marked**: the loop `continue`s (exactly as
it already did for somebody who is already a member), `status` stays `pending`
(the situation is not terminal — they may leave the other community tomorrow, and
both the correct and withdraw verbs still apply, where a fourth status would have
been a terminal state for a non-terminal situation), two new columns
`blocked_reason`/`blocked_at` record what happened, and the department is sent one
`staff_invitation.blocked` notification on the transition into blocked so the
signal does not depend on somebody opening the right tab.

`AUDIT` (ruling 3): **three of seven leadership-reachable surfaces were leaking,
and the worst of them was not leadership-specific.** Session context, the worker
snapshot's `communities[]`, the supervisor complaint reads and the hiring
conversation were already correctly scoped. The three that were not:

* `is_own_staff_assignment` (`0036`) asked "is this roster row the caller" with
  **no reference to time**, so it stayed true forever. It is the predicate behind
  the worker calendar, the job list, leave, availability, `can_read_work_order`,
  `staff_departures_read`, `security_shifts_read` and eight worker action RPCs —
  so a removed worker kept all of it. Fixed in the predicate rather than in seven
  call sites, for the reason above. **The cost is stated rather than hidden**: a
  departed worker loses their own history, which is what "removal severs access
  completely" means.
* `dm_threads_read` / `dm_messages_read` (`0046`) were keyed on the two
  participant columns alone. A thread is only ever created between two people
  `dm_pair_allowed` accepts — both active members of one community — but the read
  never asked again, so a removed supervisor kept reading every community-A
  thread including the manager's side of their own departure. The write rule and
  the read rule now say the same thing.
* `notifications_read_own` (`0041`) let a community-scoped row survive the
  membership it names.

**This overturns something already written, and names it** (as this file's own
convention requires). `0041`'s header argued, under "THE RULE THIS OVERTURNS,
STATED PLAINLY", that "a notification is a copy of something the person was
already told, and every inbox in the world retains those". Ruling 3 says
otherwise for the community-scoped ones, so the feed now hides rows whose
`recipient_membership_id` names an ended membership. **It is applied uniformly
rather than only to leadership, because it cannot be scoped to leadership**:
`remove_department_member` resets the roster row's `rank` to `member`
(`0043` §9), so after a removal nothing in the database still says the person was
a supervisor. And one message deliberately survives — `remove_department_member`
writes *"You were taken off a roster"* **after** ending the membership, so
`notify_member` now files a message addressed to an already-ended membership
against the **person** and no community. Without that, the one notification a
removed person most needs would have been written and instantly invisible, lost
to the rule meant to protect them.

`AUDIT`, out of scope but fixed because a test found it: **`HB422` was never
mapped in `pg_errors.py`.** Fifteen call sites across four migrations have raised
it since 2026-08-12 — `invite_staff_member`'s three argument checks,
`update_staff_invitation`'s three, `create_skill`'s and the complaint-routing
RPCs' — and every one surfaced as a **500 with a generic message**, which is the
API reporting its own failure for what is squarely the caller's mistake. Now a
422.

**Migration — `20260821140000_leadership_exclusivity.sql`. APPLIED and ledgered
by the repository owner, 2026-08-21** (marker corrected the same day; it read NOT
APPLIED while this entry was being written and the apply happened a few hours
later). It adds
two triggers (`staff_assignments_leadership_exclusivity`,
`service_providers_not_leadership`), two columns on `staff_invitations`, four new
predicates, rewrites six functions it does not own (`register_service_provider`,
`invite_staff_member`, `update_staff_invitation`, `claim_staff_invitations`,
`department_staff_invitations`, `is_own_staff_assignment`, `notify_member`) and
replaces three RLS policies. It **repairs nothing**: `20260812113000` §1b's
argument applies unchanged — which community loses its supervisor, and which
identity a person keeps, are somebody's job and somebody's account, so the file
counts the pre-existing violations into a `raise notice` and touches no row. It
sorts after `20260821113000` deliberately, and carries that file's
`p_location_label` forward verbatim.
`backend/tests/test_leadership_exclusivity_migration.py` checks statically what a
hand-applied file cannot get wrong: that it parses, that nothing later redeclares
what it owns, that every copied body kept the features it could have silently
deleted, that the claim's blocked branch contains no `raise`, that no statement
is destructive, and that every custom SQLSTATE it raises is mapped in Python.

Artifacts changed:

* `API.md` — §3.5 gains a paragraph on the one write that happens inside
  `GET /auth/session` and why a refused claim is invisible there **on purpose**;
  §8's leadership block gains two subsections, *Who may hold leadership* (the two
  rulings, the three entry points and how each behaves) and *Removal severs
  access* (the seven-surface leak table); the four `staff-invitations` endpoints
  gain `blockedReason`/`blockedAt` and their new 409 codes; §18's
  `POST /service-providers` gains the leadership refusal and the 503 that was
  already reachable and undocumented.
* `openapi.yaml` — `DERIVED`. `cd backend && python scripts/export_openapi.py`.
  `POST /service-providers` gains `409` and `503`; `StaffInvitation` gains two
  properties.
* `api_yaml_mapper.md` — `DERIVED`. `python scripts/regen_mapper.py`. Row content
  is unchanged apart from `API.md` line references, which moved.
* `FRONTEND_CHANGES.md` — one bullet for the blocked-invitation banner.
* `plans/MIGRATION_APPLY_RUNBOOK.md` — §14 for the new file, in the style of the
  thirteen before it, with its post-apply verification queries.
* `COMPLAINT_ENGINE_HANDOFF.md` — one entry. Nothing about the complaint
  lifecycle changed, but two of the fixes touch what a supervisor can *read* of
  it, and that boundary has an owner.

Five-gate check: **ERD** — two nullable columns on `staff_invitations`
(`blocked_reason text`, `blocked_at timestamptz`); no new table, no new
relationship. **No class-diagram change** — no new entity; the two new fields are
attributes of an existing one. **Supabase**: the migration above, and it is the
only DDL. **Component design**: no screen added or removed; `PendingInvitations`
gains one conditional line. **Frontend**: one component, listed in
`FRONTEND_CHANGES.md`.

---

## 2026-08-21 — a serviceman should not have to know his own latitude

`PO` (product owner, 2026-08-21, from live testing): **stop asking people for
coordinates.** Registration, founder onboarding and admin settings all showed the
same widget — a Latitude box, a Longitude box, and a "Use my location" button —
and that is a question almost nobody can answer about their own house. The
chosen replacement, decided in the same conversation: **type an address and press
Search, or drag a pin on a map. No API keys and no paid services**, which fixes
the upstream as OpenStreetMap: Nominatim for the geocoding, `tile.openstreetmap.org`
for the tiles, Leaflet for the map.

Why it mattered more than an ergonomics complaint. `latitude`/`longitude` are the
stored truth on `service_providers` and `communities`, and PostGIS `location` is
*generated* from them (`0034` §3, §6). A provider who skipped the field has a null
`location`, and a null `location` is invisible to `search_hireable_service_providers`
and makes `search_serviceable_communities` refuse to run at all. So the least
answerable field on the form was also the one that decided whether the account
worked. **Nothing about the distance mathematics changed here** — this is an
input-quality change and every search's geometry, radius and ordering is
byte-for-byte what it was.

`PO`: **a human-readable location label, stored and shown.** A hiring manager's
candidate card carried `distanceKm` and nothing else about where somebody is, so
"4.2 km away" had to stand in for an answer. `locationLabel` is a coarse, editable
place name — "Andheri West, Mumbai" — auto-filled from whichever gesture produced
the coordinate, capped at 120 characters.

`DERIVED`: **the cap is a privacy boundary, not a storage decision.** Hiring reads
deliberately withhold `latitude`/`longitude` (`_CANDIDATE_SELECT`, and §18 of
`API.md` says why). A label long enough for "suburb, city, state" and too short for
a street address is what keeps it on the publishable side of that line — which is
also why `GET /geo/reverse` asks the upstream for suburb-level detail rather than
trimming a building-level answer after the fact.

`DERIVED`: **the geocoder is proxied by the backend, not called from the browser.**
Nominatim's usage policy asks for an identifying `User-Agent`, at most one request
per second per application, and caching of results. A tab can honour none of the
three — script cannot set that header, and a thousand tabs cannot coordinate a
rate limit. So `GET /geo/search` and `GET /geo/reverse` exist, with a process-wide
async throttle and a bounded 24-hour cache behind them. The same policy forbids
autocomplete, which is why the search box has a button and no type-ahead; that is
a product constraint imposed by the upstream, recorded here so nobody "improves"
it later.

**Migration — `20260821113000_location_labels.sql`. APPLIED and ledgered by the
repository owner, 2026-08-21** (marker corrected the same day; it read NOT
APPLIED while this entry was being written). It adds `location_label text` (with a 1–120 `check`) to
`service_providers` and to `communities`, and then rewrites four functions and two
views to carry it: `upsert_service_provider`, `register_service_provider` and
`set_my_community_location` each gain a parameter, `create_founder_community`
reads one more key out of its payload, `service_provider_overview` and
`community_settings_overview` gain a column, and
`search_hireable_service_providers` gains a returned column. The three that gain a
parameter are **dropped and recreated rather than replaced**: a defaulted
parameter added with `create or replace` leaves an overload behind, after which
every existing PostgREST call is "function is not unique". The file is idempotent
and ends with a verification block that raises if any part of it did not take.
**Until it is applied, the code that ships with it does not work, and it is meant
not to**: three column lists ask PostgREST for `location_label` by name, so the
worker profile, the hiring candidate page and the admin settings page fail to
load, and the two provider writes answer 503 naming the rollout gap. That is the
same pattern `register_service_provider` used for its own rollout — a select list
that quietly fell back would hide an outstanding migration, and a write that
retried without the label would save a profile that lost what the person typed.
`backend/tests/test_location_label_migration.py` checks statically what a
hand-applied file cannot be allowed to get wrong — that it parses, that every
drop names the exact signature the earlier migration declared, that the hiring
search still returns no coordinates, and that every predicate deciding who is
hireable survived the rewrite verbatim.

Artifacts changed:

* `API.md` — new **§21 Address search — the location picker's proxy**: both `geo`
  endpoints with their status codes, the three-line table of what the upstream's
  usage policy asks and where each obligation is discharged, and a closing
  subsection on `locationLabel` and every payload it appears in. `locationLabel`
  also added in place to §3 (`POST /onboarding/community`, as `location_label` —
  that body is the documented `snake_case` exception), §11 (`GET`/`PUT /settings`,
  where the coordinate pair was undocumented too and now is not) and §18 (the
  provider register/read/patch, the candidate profile, and the candidate list).
* `openapi.yaml` — `DERIVED`. `cd backend && python scripts/export_openapi.py`,
  per the standing rule that it is generated and never hand-edited. Two new
  operations, one new `GeoPlace` schema, one new tag description.
* `api_yaml_mapper.md` — `DERIVED`. `python scripts/regen_mapper.py`. The
  `geo.py` section heading and its layer line are hand-written (the script
  regenerates rows inside a section, it does not invent the section); the two
  rows under it are generated.
* `FRONTEND_CHANGES.md` — one bullet for the picker and the four screens that now
  use it.
* `plans/MIGRATION_APPLY_RUNBOOK.md` — §13 for the new file, in the style of the
  twelve before it, including its own static-verification table.

Five-gate check: **ERD changes** — one nullable `text` column on each of
`service_providers` and `communities`, with a length check; no new table, no new
relationship, nothing generated. **No class-diagram change** — `GeoPlace` is a
wire DTO for a proxy and models no domain entity; the label is a field on two
entities that already exist. **Supabase**: the migration above, and it is the
only DDL. **Component design**: `LocationPicker` replaces
`LocationCoordinatesInput` at every call site, and `LocationMap` is a new lazy
leaf beneath it; no screen was added or removed. **Frontend**: four forms and two
read surfaces, listed in `FRONTEND_CHANGES.md`.

---

## 2026-08-21 — supervisors are not freelancers

`PO` (product owner, 2026-08-21, from live testing): **a manager or supervisor
hired into a department must never see "Register as a service partner."** The
marketplace registration process stays mandatory for technician-rank workers
(`staff_assignments.rank = 'member'`) and for membership-less marketplace
professionals — they are found by distance and trade, and the form is where the
coordinates and skills that find them come from. Leadership is not found: an
administrator typed their name and their email, and nobody will ever match them
by radius.

The defect, exactly. `claim_staff_invitations` (`20260812090200` §4) writes a
`community_memberships` row and a `staff_assignments` row keyed on the
**membership** and **no `service_providers` row**. Every provider-keyed read is
therefore blind to leadership: `service_engagement_overview` joins
`service_providers` and filters `service_provider_id is not null` (`0035`
418–444), and `GET /worker/snapshot` returned an empty snapshot the moment
`service_providers_service.get_mine` raised. So an invited supervisor arrived at
`/worker` looking exactly like somebody who had never registered — and the
layout put a marketplace form in front of them. The same empty `communities`
took their Complaints screen with it, since that screen decides supervisor
access from `communities[].rank`.

`DERIVED`: `provider` and `communities` answer two different questions and are
now asked separately.

* `API.md` § the worker's portal — `GET /worker/snapshot` documents that
  `communities` is populated independently of `provider`, that `provider: null`
  beside a non-empty `communities` is department leadership, and that a client
  must decide the registration form on `provider` **and** `communities[].rank`
  rather than on `provider` alone. It also names which of the two reads answers
  for which caller, and why the membership-keyed one carries no `departure`.
* `GET /worker/communities` is deliberately **unchanged** and still `404`s an
  unregistered caller. There the difference between *you have not registered*
  and *nobody has hired you* is the endpoint's whole point, and the dashboard
  routes on it; widening it would have made one contract serve two questions.
  The worker portal's "Where I work" panel reads the snapshot instead when there
  is no provider profile.
* `openapi.yaml` and `api_yaml_mapper.md` regenerated. No schema changed —
  `WorkerSnapshot` already carried `communities[].rank`; what changed is which
  callers get rows in it. (The regeneration also picked up the 2026-08-20
  remember-me descriptions, which had not been exported.)
* `FRONTEND_CHANGES.md` — one bullet for the layout gate and the four screens
  that now say plainly that there is no marketplace profile.

No migration was needed and none was written. The membership-keyed read is
backend code only: `community_memberships`, `staff_assignments`, `departments`
and `communities` are read with the service client keyed on the caller's own
`profile_id`, which is the same path `auth_service._active_memberships` and
`_portal_for` already take on every session read — so it is known to work on the
hosted project without touching hosted DDL.

Five-gate check: no ERD change (nothing stored is new — the roster rows and
memberships already existed), no class-diagram change (no new type; the two
existing engagement reads are both `HiringService` methods), no Supabase change,
and the component design's worker portal keeps every screen it had.

---

## 2026-08-21 — the notification rewriter learns the worker portal

`PO` (product owner, 2026-08-21): **fix the routing, do not widen it.** The
notification urls stay admin-shaped in SQL — SQL does not know who will read
them — and the per-reader rewrite in
`frontend/src/features/notifications/portalUrl.js` stays the single place that
answers "where does *this* person go".

The defect. That module's `PORTAL_BASES` knew `manager` and `security-manager`.
A service department's supervisor is neither: `_portal_for`
(`auth_service.py:248`) upgrades only a `security`-role membership by roster
rank, so a `worker`-role supervisor stays `worker`. Their `/admin/…` links came
back unrewritten, hit `ProtectedRoute requiredRole="Admin"`, and redirected home
— a click that appears to do nothing, which is
`docs/potential issues/14` for the third time and one portal over. Two families
reach them now: the five work-order kinds keyed to
`work_orders.supervisor_membership_id`, and the complaint staff notices
`notify_complaint_staff` widened to supervisor-rank roster holders (R18,
`20260821200000`).

`DERIVED`: the rule table became **per-portal** rather than gaining a third row
of the same shape, because `/worker` does not mount the same screens.

| Path under `/admin` | `manager` | `security-manager` | `worker` |
|---|---|---|---|
| `departments/{id}/work-orders` | rewritten | rewritten | **rewritten** |
| `departments/{id}/hiring`, `staff/{id}`, `candidates/{id}` | rewritten | rewritten | **left alone** — no such screen |
| `departments/{id}` (root) | → portal base | → portal base | **left alone** — a worker's base is a jobs dashboard, not a department |
| `complaints` | rewritten | left alone | **rewritten** |
| `messages` | rewritten | rewritten | **rewritten** |
| `security/incidents` | left alone | → `/security-manager/incidents` | left alone |
| `amenities`, `complaint-triage` | left alone | left alone | left alone |

The three "left alone" rows for a worker are the module's own doctrine held
rather than bent: a rewrite to a route that does not exist fails more
confusingly than one that visibly bounces. A rank-`member` technician shares the
`worker` portal and a rewritten work-order link lands them on the triage
wrapper's in-page refusal panel instead of silently home — visible and
self-explaining, so an improvement. Rank is not on the session, and this module
keys on portal only.

* `backend/tests/test_notification_links.py` mirrors that table in Python by
  design and was restructured in lockstep: per-portal `_SUBSCREENS`, a new
  `UNREWRITTEN_FOR_A_WORKER` record, and the mirror test now compares
  dictionary against dictionary and reads the two `new Set([…])` portal lists by
  content — so reverting the JavaScript half, or quietly handing `worker` the
  manager's four sub-screens, still fails loudly. The record entries also became
  whole paths matched exactly rather than prefixes matched with `startswith`,
  because a department-root prefix would otherwise have silently excused the two
  sub-screen entries beneath it.
* `portalUrl.test.js` — **new file**. The module had no test of its own; the
  Python mirror is compared with its source text, not run against it, so an
  object looked up with the wrong key or a `Set` membership inverted was
  invisible to both halves.
* `docs/potential issues/14-…` — the third recurrence written up, and one new
  line in "What is still not fixed".

**Recorded, not fixed**: `WorkerDashboard/Complaints.jsx` reads no query
parameter, so a supervisor sent `?complaint=` now lands on the right screen and
the wrong row. That screen belongs to the complaint-engine owner
(`COMPLAINT_ENGINE_HANDOFF.md`) and highlighting a row there is their call. It
is not in `IGNORED_QUERY_PARAMETERS` because that check reads the emitted
`/admin/complaints`, already on record, rather than the per-reader rewrite.

No migration, no DDL, no API surface change — so `API.md`, `openapi.yaml` and
the mapper are deliberately untouched. Five-gate check: no ERD change (nothing
is stored), no class-diagram change (no new type), no Supabase change, and the
component design's screens are the ones already mounted.

---

## 2026-08-21 — the deep link lands on the row, and the department root is rewritten after all

`PO` (product owner, 2026-08-21), two rulings closing the two findings the
notification-links workstream left open earlier the same day. Both are
frontend-only: no migration, no DDL, no API surface change.

**Ruling A — `?complaint=` must highlight, on the worker screen and the admin
screen.** The resident screen stays untouched while that portal is still a
dummy-data demo (`docs/potential issues/09-…`), which is a deferral with a
reason rather than an oversight: highlighting a row in fixture data proves
nothing.

`DERIVED`, worker screen: nothing was missing but a prop.
`features/complaints/components/DepartmentComplaintList` has taken `highlightId`
and ringed that card since the manager's screen was built, and
`WorkerDashboard/Complaints.jsx` renders that exact component — it read the
parameter nowhere and passed the prop never. The `canMove={false}` rule and the
roster gate are untouched.

`DERIVED`, admin screen: a different surface, so a different idiom.
`AdminDashboard/Complaints.jsx` renders the dashboard snapshot's `complaints`
projection out of the zustand store rather than the shared department list, so
the named card gets `border-2 border-indigo-400 bg-indigo-50/40` in place of its
hairline border, `aria-current="true"` so the mark is not colour-only, and a
scroll into view once the snapshot arrives. **Marked, never filtered** — the
same rule the shared list and `WorkOrderTriage`'s `?job=` follow, because a
queue narrowed to one card hides the rest of an inbox somebody still has to
work. No complaint lifecycle behaviour, mutation or route was touched; that
surface is the complaint-engine owner's and the ruling is recorded for them in
`COMPLAINT_ENGINE_HANDOFF.md` §16.

`AUDIT`: `("/admin/complaints", "complaint")` has left
`IGNORED_QUERY_PARAMETERS` in `backend/tests/test_notification_links.py`. That
assertion is equality precisely so a screen which starts honouring its parameter
is a test change rather than a silent improvement, and this is the mechanism
earning its keep for the first time. `("/resident/complaints", "complaint")`
stays on record. The docstring paragraph the earlier workstream added — that a
supervisor now lands on the right screen and the wrong row — was a true
statement for one day and is now the history of one, so it says so.

**Ruling B — the department-root link is rewritten for a `worker` reader too**,
overturning the reading recorded four sections above, where the row
`departments/{id} (root)` said *left alone — a worker's base is a jobs
dashboard, not a department*. That is true about the screens and answers the
wrong question. `/admin/departments/{id}` is Admin-guarded, so a worker-portal
reader who follows it is redirected to `/worker` by `ProtectedRoute` whatever
the rewriter does; the choice was never between two destinations but between
reaching their portal home deliberately and reaching it via a click that
appeared to fail. `worker` joins `DEPARTMENT_ROOT_PORTALS`.

They are a real audience for that url, not a hypothetical one produced by the
mirror test's deliberately blind every-portal check:
`notify_department_leadership` (`0043_staff_departures.sql` §419–436) includes
supervisor-rank roster holders, who hold portal `worker`, and
`staff_invitation.blocked` (`20260821170000`) carries `/admin/departments/{id}`.

`DERIVED`: the doctrine in `portalUrl.js`'s header is intact. It forbids
rewriting to a route that **does not exist**; every portal's base exists. This
is the one rule in that table which does not point at a screen the portal
mounts, and the module says so out loud rather than leaving it to be discovered.
The hiring, staff and candidates rows for `worker` are unchanged and stay
bouncing — those *are* missing screens.

`PO`, explicitly: **no migration.** Redeclaring `claim_staff_invitations` to
change the url it writes was considered and rejected — the same function has now
been redeclared repeatedly, the fix belongs at the point of the click where the
reader's portal is known, and the rewriter already answers that question.

* `frontend/src/features/notifications/portalUrl.js`,
  `backend/tests/test_notification_links.py` (`_DEPARTMENT_ROOT_PORTALS`) — the
  two halves change in lockstep or the mirror test fails by content comparison,
  which is what it was rebuilt for earlier the same day.
* `/admin/departments/{param}` left `UNREWRITTEN_FOR_A_WORKER`. It was the only
  line in that record naming a live audience; the three that remain are all "no
  such screen in this portal".
* `portalUrl.test.js` — the worker department-root case flips from *unchanged*
  to *→ `/worker`*, with the sub-screen precedence pinned beside it so the root
  rule can never swallow a `work-orders` link and throw its `?job=` away.
* `docs/potential issues/14-…` — the `?complaint=` remainder and the
  department-root remainder both close; the hiring/staff-links-to-supervisors
  remainder stays recorded, because it is still true.

Five-gate check: no ERD change (nothing is stored), no class-diagram change (no
new type), no Supabase change, no component-design change (both screens were
already mounted; one gained a highlight), and the frontend change is the one
described above. `API.md`, `openapi.yaml` and the mapper are deliberately
untouched — no endpoint moved.

---

## 2026-08-20 — "Remember me", and a login page that is actually there

`PO` (product owner, 2026-08-20): **the login page must always appear unless the
person explicitly opted into staying signed in.** Until now every successful
sign-in wrote a refresh cookie with `Max-Age = AUTH_SESSION_IDLE_DAYS` (30 days),
so a returning visitor was silently signed back in and the sign-in card's
existing redirect forwarded them straight to their portal. On a shared or public
browser that is the wrong default: the second person to open it lands inside the
first person's account. The redirect itself is correct and stays — it is the
autologin mechanism, and it should only fire for people who asked for it.

`DERIVED`: consent has to be asked once and then honoured on all three paths that
mint a session, so the change is one decision (`persist`) threaded through each:

* `API.md` § 1.2 — the cookie table gains `__Host-hb_remember` and a paragraph
  stating the contract explicitly: access and CSRF cookies keep their ~1h life;
  the refresh cookie is written **without `Max-Age`** (a browser-session cookie)
  unless the sign-in asked to be remembered. The remember cookie exists only so
  `POST /auth/refresh` can carry the answer across token rotation — it holds no
  secret, so it is not signed; the worst a user can do by editing it is change
  how long their own session lasts.
* `API.md` § 3.2 — `GET /auth/oauth/{provider}/start` (and the `/google/start`
  alias) documents the `remember` query parameter. The provider round trip has
  nowhere to keep it, so it rides in the signed PKCE transaction cookie and is
  read back by the callback.
* `API.md` § 3.3 — `POST /auth/password/sign-in` documents `remember_me`,
  default `false`. `POST /auth/email/verify` is documented as never persistent:
  the confirmation link never asked the question, so it takes the safe answer.
* `API.md` § 3.5 — `POST /auth/refresh` re-issues the persistence the sign-in
  chose rather than defaulting; `POST /auth/logout` clears the remember cookie,
  so signing out ends autologin instead of leaving it armed for the next person.
* `openapi.yaml` and `api_yaml_mapper.md` regenerated. The mapper's auth section
  gained a note, because the feature is spelled three different ways (a body
  field, a query parameter, a cookie) and appears in no response schema, so the
  generated rows cannot show it.
* `FRONTEND_CHANGES.md` — the auth-client bullet list now names the checkbox and
  both spellings it produces, since that file describes what the client sends.

Five-gate check: no ERD change (this is cookie lifetime, not stored state), no
Supabase change, and the class diagram lists `WebSession.establish_session()`
without a parameter list, so its new `persist` argument does not appear there.
Frontend and API docs are the two gates that moved.

## 2026-08-20 (merge) — live-app-fixes reconciled with main

`AUDIT`: merging `origin/main` (the services-and-security merge, PR #35) into
`live-app-fixes` conflicted in five files. This log and
`COMPLAINT_ENGINE_HANDOFF.md` kept both sides' entries; `Header.jsx` took main's
snapshot-backed residency chip, which subsumes this branch's hide-missing-tower
fix; `openapi.yaml` and `api_yaml_mapper.md` were regenerated from the merged
code rather than line-merged; `Departments.jsx` was merged semantically so both
sides' fixes survive.

## 2026-08-20 (later still) — Q12.1 answered, Q12.2 closed

`PO`: the resident **is** to be notified when a complaint is raised on their
behalf — the explicit "yes" Q12.1 was waiting for; the mechanism stays with the
complaint-engine owner and nothing is implemented yet. `AUDIT`: Q12.2 closed by
running its `pg_proc` query on the hosted database after applying
`20260820150000` — exactly two rows (`raise_complaint` at 8 args,
`admin_raise_complaint` at 9), no orphaned overload. Both recorded in
`COMPLAINT_ENGINE_HANDOFF.md` §12.

## 2026-08-20 (later) — On-behalf complaints get two valid actors

`PO` (product owner, 2026-08-20, fifth ruling of the day): on an on-behalf
complaint, **both** the resident and the admin hold the lifecycle verbs (cancel,
reschedule, …); either's action is valid and whoever acts first wins.
`COMPLAINT_ENGINE_HANDOFF.md` §12 gained an addendum recording the ruling, the
current-state gap it exposes (the admin `PATCH` accepts only
`Pending | In Progress | Resolved`, so admins currently have **no** cancel or
reschedule verb anywhere), and the note that the ruling half-answers Q12.1 — a
resident expected to act on a complaint has to be told it exists. The design of
the admin-side verbs stays with the complaint-engine owner; nothing was
implemented.

## 2026-08-20 — Admins raise complaints, and "resident" stops meaning the role column

`PO` (product owner, 2026-08-20, four rulings): an admin who holds a flat **is**
the resident of that flat; admins raise complaints **from the admin portal**,
either on a resident's behalf or attached to no unit; provenance belongs in the
`raised` event and not on the complaint row; and the resident raise is a resident
act. The endpoint, the guard and the column that implement them were built the
same day. Documented here after reading the merged code rather than the interface
spec that preceded it. **The two disagree in three places and the code is what is
written down**, since the code is what a client will meet:

1. **`category` is optional on `POST /complaints/admin-raise`**, not required as
   the spec's request shape had it. A caller sending `skillId` gets the trade's
   current name snapshotted into `category` by the RPC, exactly as on the
   resident's form; requiring both would make the admin's trade picker send a
   string it does not have. *"A complaint needs a category"* is enforced once, in
   `admin_raise_complaint`, and surfaces as a `422`.
2. **The session layer no longer grants an admin the `resident` capability
   unconditionally.** The spec cited that unconditional grant as an existing fact
   in support of the ruling; implementing the ruling made it wrong, because the
   guard and the session would then answer the same question from the same table
   and disagree for a flat-less admin. `GET /auth/session` now requires the
   residency too.
3. **A reported orphan `raise_complaint` overload does not survive reading the
   migrations.** Recorded in the handoff §12 Q12.2 as *checked and not upheld*,
   with the narrower question that *is* open — the hosted probe cannot see
   overloads at all — left standing for the engine's owner.

### docs/API.md — the new endpoint, and one guard rule stated once

`DERIVED`. **New §7.2, "Who holds the resident verbs"**, is the rule in one place
so that seven endpoints can point at it instead of restating it seven ways:
resident-ness is an active `unit_residencies` row, never an implication of the
role column, because there is one membership row per person per community and the
administrator who owns B-402 has exactly one and it says `admin`.
`require_resident_capability` replaced `require_membership_role("resident")` on
`/cancel`, `/reopen`, `/resolution` and both resident-scheduling routes, whose
sections now say "the resident capability" rather than "`RESIDENT`".

**New section `POST /api/v1/complaints/admin-raise`** — request, `201
{id, message}`, the two modes and the full status table (`403` twice over, `404`
for an unknown trade, `422` for priority and for a complaint with neither category
nor skill). Placed with the other admin writes, since it is on `complaints.py` and
guarded by `require_admin` + CSRF.

**A behaviour NARROWING, recorded as its own note rather than folded into the
widening.** `POST /complaints` required only an *active membership*; it now
requires the resident capability, so a `worker`, `security` or `manager`
membership with no residency gets `403 community_role_required` where it
previously filed a complaint onto a resident list. This is the one change in the
session that can take something away from somebody. It was checked before being
written down: **no screen outside the resident portal calls `POST /complaints`**
(swept across `frontend/src/**` on 2026-08-20), and an admin's path is
`/admin-raise`. Recorded at the endpoint, in §7.2, in the API.md §17 changelog and
here, because a narrowing that is only mentioned where it is convenient is how a
`403` becomes a support ticket.

Also: `GET /complaints` and `GET /complaints/{id}` now say they filter
`raised_via = 'resident'`; §1.2's capability note says the `resident` capability
is granted to an admin only with a residency; the banner and §16.6's totals were
recounted (below).

### docs/openapi.yaml — regenerated, not edited

`DERIVED`. `cd backend && python scripts/export_openapi.py`, per the standing rule
at the head of `API.md`. Adds one operation and two components
(`AdminRaiseComplaintRequest`, `AdminComplaintRaised`).
`tests/test_openapi_spec.py` passes (30 tests), and `--check` is clean.

**Nothing else in the spec moved, and that is the finding.** Six routes changed
who may call them and not one path, body, response model or status code changed
with them, so the generated spec is byte-identical on all six. A guard change is
invisible to every mechanical check this project has; it exists only in the prose
of `API.md` §7.2 and the mapper's router notes. Same class as the `0041`
notification move logged in the mapper's §7 on 2026-08-10.

### docs/api_yaml_mapper.md — §3 regenerated, notes added by hand

`DERIVED`. `python scripts/regen_mapper.py`, per §6.1 step 4 — *do not hand-write
the row*. One row added under `complaints.py`; **126 existing rows changed**, every
one of them an `API.md:NNNN` reference moved by this session's edits or a handler
line number in one of the three touched routers. Hand-written notes added under
`complaints.py` (why the endpoint is there and not on the resident router, and
why the path cannot collide), under `resident_complaints.py` (five widenings and
one narrowing, plus the repository's new `raised_via` filter) and under
`resident_scheduling.py` (the guard swap, with the no-wire-change consequence).

*(One trap recorded in that file's own changelog: `regen_mapper.py` printed "815
row(s) differ". It zips old against new line-for-line, so a single inserted row
makes everything below it compare unequal. The real number is 126.)*

### docs/CHANGE_LOG.md and docs/API.md — three counts found stale, and the drift is not ours

`AUDIT`. `API.md`'s banner said **195 operations across 164 paths** and §16.6 said
**122 of 195**; the generated spec at `ed9a131` — before this session touched
anything — already held **198 across 167**. So three operations had arrived
without either number moving, and this session's one endpoint makes four. Both
lines now read the counted value (**199 across 168**, and 124 of 199 serving no
story, with 75 serving one), with the earlier figures kept in place rather than
overwritten. The mapper's header and §5 got the same treatment. **The test total
in the mapper's header was deliberately not touched**: only
`tests/test_openapi_spec.py` was run in this pass, and replacing one unverified
count with another is how these lines got stale in the first place.

### docs/COMPLAINT_ENGINE_HANDOFF.md — §12, the rulings, and two questions

`PO` → recorded as **decisions, not open questions**, which is the reverse of
every other section in that file and is why §12 opens by saying so. D1 the
residency guard (and the matching `GET /auth/session` correction), D2 the
two-mode endpoint, D3 provenance in the `raised` event with `raised_via` as the
narrower *which-portal-owns-the-view* flag, D4 the resident-raise narrowing. Names
the migration (`20260820150000_admin_raised_complaints.sql`, applied by hand by
the repository owner) and asks the owner to review `admin_raise_complaint`'s
semantics, since the complaint lifecycle is theirs.

Two genuinely open questions were added for that owner:

- **Q12.1 — nobody tells the resident.** `admin_raise_complaint` calls
  `notify_complaint_staff`, exactly as `raise_complaint` does, so a resident who
  telephoned the office now owns a complaint with an SLA clock and three verbs and
  has no signal that it exists. The default was inherited rather than chosen.
- **Q12.2 — a claimed orphan `raise_complaint` overload, checked and not upheld.**
  It was reported that `20260812090300` rebuilt the function at a new arity
  without dropping the old one. `20260812090300`:271 **does** drop the six-argument
  signature, and `20260813100000`:75 drops the seven, both exactly. What survives
  as a real question is narrower: the hosted probe reads PostgREST, which lists
  one entry per RPC name and therefore **cannot see an overload at all** — so one
  `pg_proc` query is worth running, and `0031`:410 granted the six-argument version
  to `authenticated`, which is what would make a survivor reachable rather than
  merely present. Written up as a verification item, not as a defect.

### docs/COMPLAINT_ENGINE_STATE.md — the orientation document said one thing that is now false

`AUDIT` → `DERIVED`. §2 opened with **"today there is exactly one origin: the
resident"**, which stopped being true the moment `/admin-raise` merged, and the
handoff points every new reader at this file *first*. Rewritten to two origins,
with the mode table and the `raised_via`-is-not-provenance distinction. §8's
resident heading said *"resident role only"* — now the capability, with the
`raised_via` read filter noted on the list and the detail; the admin table gained
`/admin-raise` and the staff detail read it had never listed. §7 gained the fact
that **no notification reaches the raiser**, which was harmless while the raiser
was always the person pressing the button. §9 gained the admin raise modal. §10
item 6, *"a staff-side origin for complaints"*, is **half-closed**: an admin has a
path, the **gate still does not**, and saying "closed" would lose the half that
matters to a guard taking a walk-in.

### Pending reconciliation — the ERD and the class diagram do not know about `raised_via`

`AUDIT`, and deliberately **not fixed here**: `docs/erd/homebandhu.dbml` and
`docs/class-diagram/homebandhu-domain.puml` are not this session's artifacts, and
a diagram edited from one column's point of view is worse than one that is
knowingly behind.

- **`erd/homebandhu.dbml`** `Table complaints` (:543) has no `raised_via`. It
  needs `raised_via text [not null, default: 'resident']` with the CHECK noted, and
  a comment saying what it is *not* — it is which portal owns the raiser-side
  view, and **not** provenance, which lives in the `raised` event payload
  (`on_behalf`). That distinction is the whole ruling and a column added without it
  will be read as "who filed this".
- **`class-diagram/homebandhu-domain.puml`** `class Complaint` (:499) needs the
  same as an attribute (`raisedVia : RaisedVia`), and the aggregate's behaviour
  note should record that the raiser and the actor of the `raised` event can now
  be different people — which is the part a class diagram can express and a column
  cannot.
- **The wider divergence on this table is older than today** and is *not* created
  by this change: the ERD still carries `unit_id`, `urgency`, `sla_due_at`,
  `reopen_count`, `resident_rating` and `version` where the database has
  `priority`, `expected_resolution_at`, `reopened_count`, `resolution_rating` and
  `aggregate_version`. Whoever reconciles `raised_via` will be standing in front of
  all of it; that is a reconciliation pass, not an amendment.

---

## 2026-08-20 — The hosted database is not a baseline database

### docs/HOSTED_SCHEMA_DRIFT_COMPLAINTS.md — new

`AUDIT` (found live: `POST /api/v1/complaints` returned 400 "Could not raise the
complaint."; the real error, surfaced by the new logging in
`app/core/pg_errors.py`, was `42703: column "payload" of relation
"complaint_events" does not exist`). A read-only probe of the linked hosted
project — column selects plus PostgREST's own OpenAPI description of the schema,
which reports nullability and every RPC's argument list without touching a row —
established the cause and its shape. **The linked project was never created from
`0001_baseline.sql`.** It carries the pre-baseline complaint tables
(`complaint_events.previous_status/new_status/note`, `complaints.unit_id`,
`complaints.closed_at`), and every migration from `0018` onward extends them with
`add column if not exists`, so all of them applied cleanly and none of them
supplied a column that *only* the baseline declares. Exactly two such columns
exist on this surface, and both are missing: `complaint_events.payload` (breaks
45 insert sites across 12 migrations — every complaint write plus the resident
timeline *read*) and `complaints.aggregate_version` (breaks the four RPCs behind
`PATCH /complaints/{id}`, reopen, confirm and comment — a second failure hiding
behind the first, found by probing rather than by any stack trace). A third gap
is hosted-only in the other direction: `complaints.description` is `not null`
while the baseline and the wire schema both make it optional. The new document
records expected-versus-found with the probe behind each line, what each gap
breaks by user-visible action, the 105 columns across 12 tables, 2 views and 30
functions that were probed and found **correct** (all seven Complaint Engine v2
migrations are applied, at the right arities), the objects PostgREST cannot verify at all
(triggers and CHECK constraints), and the apply-and-verify runbook.

### docs/COMPLAINT_ENGINE_HANDOFF.md — §11, may a complaint have no description?

`AUDIT` → `DERIVED`. Reconciling the two missing columns is bookkeeping and was
done. The `not null` on `description` is not: the wire makes the field optional
(`_optional_text(4000) = ""`) and `raise_complaint` writes a real null for it, so
the hosted column and the API contract disagree about what a complaint is. The
default taken is the repository's own declaration — the constraint is dropped, a
complaint may be filed with a title and a category and nothing else — and the
question of whether that is *right* is logged for the engine's owner, together
with the note that making it mandatory belongs on the wire rather than back on
the column. §11 also records that the legacy `note`/`new_status` columns were
left in place and nothing was backfilled into `payload`, because all five
complaint-engine tables held 0 rows on the probe date.

**Not a `docs/` artifact, listed here because §11 and the drift report both point
at it:** the fix is
`backend/supabase/migrations/20260820120000_hosted_complaint_column_drift.sql` —
a forward-only timestamped migration, per `backend/supabase/migrations/README.md`,
rather than a new `patches/` directory. It adds the two columns, drops the one
constraint, redefines no function (none was stale) and re-checks all three in the
same transaction.

---

## 2026-08-19 — The departments pages stopped rendering the skeleton

### docs/FRONTEND_WIRING_AUDIT.md — the department reads are now actually called

`AUDIT` (found live: the department edit form prefilled only name, description and status —
categories, skills, SLA, head, contacts and hours came up blank however much was saved — and the
department cards showed no category chips). The audit's own §1 exception said the snapshot cannot
feed `Departments.jsx` and `DepartmentDetail.jsx` and that `GET /departments` is the only source,
but neither page was ever pointed at it: both rendered the store's snapshot copy, which is the
hardcoded `{staff: [], categories: []}` skeleton (`dashboard_service.py:203`). `Departments.jsx`
now reads `GET /departments?pageSize=100` via react-query (`['departments']`), and
`DepartmentDetail.jsx` reads its header from the same payload its roster query already fetched.
The zustand slice keeps the writes (toasts, activity log, guards); each page invalidates the
query key after one, so the UI shows the server's answer rather than the optimistic copy. The
§1 exception, the §2 table rows for both pages, and the §6 item about the stub were annotated
to record that the endpoints named there as "the only source" are now the source in fact.

---

## 2026-08-19 — The session learned to name the flat

### `GET /auth/session` now carries `membership.unit` — API.md §3.5, openapi.yaml, api_yaml_mapper.md

`AUDIT` (found live: every portal's header chip read "Flat — • Tower —"). The session response
carried only the opaque `membership.unit_id`, and `applicationUser()` in the frontend hard-coded
the placeholders because no endpoint returned a human-readable label — the gap
`ResidentDashboard/Profile.jsx` had recorded as a blocker. The membership now embeds
`unit: { unit_code, unit_type, building_name, building_type }`, read from `units` and its
building in one PostgREST query; `building_*` is null for standalone homes (`units.building_id`
is null — community type is apartment XOR standalone homes, per the 2026-07-28 ruling), and
`unit` itself is null when there is no residency or the lookup fails, because display data must
never fail an otherwise-valid session. §3.5 gained the response fragment; `openapi.yaml` and the
mapper tables were regenerated (`MembershipUnit` schema added; the session row's editorial cell
repointed from §1.2 to §3.5, where the shape is now documented). The header renders the real
labels and drops the "• Tower …" half when there is no building to name.

## 2026-08-12 — Session 75: Complaint Engine v2 — PRD, implementation plan, testing docs

### docs/COMPLAINT_ENGINE_PRD.md — new

`PO` (structured decision session, 2026-08-12; nineteen rulings, tabled in the PRD's §12 ledger and
mirrored into the handoff's new §11). Specifies the target complaint engine end to end: manual-first
assignment with worker consent (offer, not instant assignment — **overturns** `assign_work_order`'s
built write-accepted-without-asking semantics), forced assignment for high-priority all-declined jobs
(best-ranked instant, not random), auto-dispatch demoted to a 2h/24h fallback, `high` = critical (no
fourth priority level), freeform in-chat price negotiation (no money schema), skill-sourced categories
(one catalogue feeds the resident dropdown and provider onboarding — **overturns** the raise dialog's
`complaint_categories` sourcing), status coupling via a forward-only projection (**settles** handoff
§0/§1), resident cancel with a re-evaluation pool, 72h auto-close with a 48h reminder (**settles**
handoff §2, overturning the product doc's literal 24h), reopen-to-same-queue-with-worker-exclusion
(**settles** handoff §4, retiring the different-supervisor clause), the admin assign control replaced
by raise-work (**settles** handoff §8/§10 option 1), work on terminal complaints refused (**settles**
handoff §10), transfers with live work refused, and the timeline vocabulary CHECK-locked.

### docs/plans/COMPLAINT_ENGINE_V2_IMPLEMENTATION_PLAN.md — new

`DERIVED` (from the PRD). Six new migrations (`20260813100000`–`20260813105000`), backend/frontend
task breakdown with the repo's rebuild-whole-with-CHANGED-markers convention, and the full testing
suite plan (39 SQL behaviour assertions, API/vitest additions, eight end-to-end workflow sweeps).

### docs/COMPLAINT_ENGINE_MANUAL_TESTING.md — new

`DERIVED`. Per-role manual walkthroughs (resident, supervisor/manager, worker, admin) plus the
15-minute cross-role regression sweep.

### docs/COMPLAINT_ENGINE_HANDOFF.md — §11 appended

`PO`. The rulings ledger, so the handoff's open questions visibly close where they were opened.

---

## 2026-08-12 — Session 74: CI diagnosis, and a runbook addendum for the two pulled privilege migrations

### docs/plans/MIGRATION_APPLY_RUNBOOK.md — addendum §10–§12

`AUDIT` (CI's red `database-browser` job prompted the dig; the teammate's fix commit `b9ab138`
resolved it and brought two migrations the hosted project does not have). The addendum covers
applying `20260812190000_grant_service_role_data_access.sql` and
`20260812200000_enable_authenticated_request_client_reads.sql` in the SQL Editor, with per-file
post-checks and the two ledger inserts (47 → 49). Verified statically before writing: both files
parse, conflict with nothing applied, and every statement is re-run safe.

The load-bearing finding, recorded in the addendum's "why promptly" note: **no migration in the
chain ever enabled RLS on `staff_assignments`** — the repositories and the security-invoker
`department_staff_overview` view were written assuming it was on. On hosted, roster reads work
today only through Supabase's default grants, unscoped by any policy; `20260812200000` is what
turns the scoping on. Two notes deliberately recorded rather than fixed (the migration is the
teammate's): the blanket grant-select loop undoes the deny-by-default `revoke all` posture on
server-only tables (still deny in practice — no policies exist), and the `for all` admin-write
policy is paired with an `insert, update`-only grant, so a JWT-path delete would fail with a
privilege error instead of a policy refusal — latent, since the only direct table access is the
service client (`auth_service.py:289`).

### docs/API.md §5 — `GET /dashboard/snapshot` gains `weeklyNew`

`DERIVED` (the fix for the live snapshot 500 shipped alongside the field the dashboard chips
needed). The hosted project is a legacy database with every repository migration applied on top,
so `0032` renamed its visitor event log to `legacy_visitor_events` and `0023` renamed its booking
series tables to `legacy_amenity_booking_*` — but `dashboard_repository.py`'s legacy branch still
read the old names, and PostgREST's PGRST200 on the `visitor_events` embed 500'd the whole
snapshot. The projections now read the renamed tables. While there, the snapshot response gained a
top-level `weeklyNew` object — `{residents, complaints, visitorRequests, bookings}`, integer
counts of rows created in the trailing 7 days, always present, `0` when none, computed as
head-only count queries — replacing the frontend's hardcoded "+2 this week" chips. Documented in
§5 because the rest of the snapshot's contract predates this workstream.

### docs/openapi.yaml, docs/api_yaml_mapper.md — regenerated

`DERIVED`. The spec picked up `WeeklyNewCounts` and the snapshot description; the mapper re-run
re-resolved handler line numbers in `dashboard.py` and the `API.md` line references that moved
below the new §5 block.

### Frontend shell — a portal error boundary, and the header chip tells the truth

`PO` (the owner's first live admin walk surfaced all four defects; the fixes are `DERIVED`).
Three shell-level decisions worth recording beyond the bug fixes themselves:

- **Every portal layout now wraps its `<Outlet />` in `PortalErrorBoundary`**
  (`components/common/PortalErrorBoundary.jsx`). The trigger was a missing `useQuery` import in
  `Departments.jsx` unmounting the entire app to a blank page; the boundary contains any future
  render crash to a "Something went wrong here" panel with a retry, self-resetting on navigation.
  Five layouts, five one-line wraps — they share no common shell to mount it once.
- **The header residency chip reads the snapshot's `users` projection, not the session.**
  `currentUser.flat`/`tower` were hard-coded `'—'` placeholders in `applicationUser()` and never
  real; the chip now finds the signed-in member's own row (unit_residencies → units → buildings)
  and **hides entirely when there is no unit** — an admin with no residency gets no chip, not
  dashes. The `'—'` placeholders stay on `applicationUser()` because two demo-era slices still
  stringify them; nothing user-facing reads them any more.
- **Trend chips render only from `weeklyNew`.** The hardcoded "+2 this week" strings are gone;
  a chip renders `+N this week` only for a finite count > 0, so a missing field, a zero, or a
  down snapshot all render nothing rather than an invented number. The landing page's fake
  "12 new this month" stays — it is inside the marketing illustration, not a data surface.

### Both snapshots read concurrently — wall time drops from sum-of-RTTs to max

`PO` (the owner reported the amenities tab "takes a long time"; the mechanism is `DERIVED`).
The admin snapshot issued 15–16 synchronous PostgREST round trips in strict sequence, the
resident snapshot 6 — wall time was the *sum* of the RTTs to the hosted project. Nothing except
legacy payments (which filters by the invoice ids just fetched) depends on another read, so both
services now fan the reads out over a bounded `ThreadPoolExecutor` (invoices→payments chained
inside one worker) and assemble identically — ~8× in simulation. The shared supabase client was
verified thread-safe for this fan-out against the installed sources: `table()` builds a fresh
request builder per call, httpx's session is documented thread-safe, and the lazily-initialised
`client.postgrest` is forced on the calling thread by the schema probe before any worker starts.
Wire shape unchanged (`export_openapi.py --check` untouched); a failing read still fails the
whole request with its own exception, never a partial snapshot.

### Departments form — one manager entry, and modals escape the fade-in trap

`PO` (the owner found the create form carrying two generations of manager entry and the modal
clipped under the header). Two rulings worth a record:

- **The invitation block is the only place a manager is entered.** The legacy free-text
  "Department Manager" input is gone; `head` is derived at submit from the first Manager row's
  name (an edit with no re-entered leadership preserves the stored head). The contact email/phone
  pair stays but is relabelled "Department contact …" — it describes the department, not a person.
- **The modal defect was a stacking-context trap, and the fix is portals.** `.animate-fade-in`
  uses `fill-mode: forwards`, and an animation that targets opacity keeps its element a stacking
  context for as long as it is applied — which `forwards` makes forever. Every portal layout puts
  that class on `<main>`, so any `fixed` overlay rendered in place is trapped below the `z-40`
  header no matter its own z-index. The two departments modals now render through
  `createPortal(document.body)` (the repo's first; no utility existed). Other in-place overlays
  (amenity form modal, booking ModalLayout) share the latent trap and are flagged, not touched.

## 2026-08-12 — Complaint Engine v2

- `API.md`, `openapi.yaml`, and `api_yaml_mapper.md`: documented and regenerated the skill-based raise, resident cancel, candidate picker, and staff detail API surface.
- `design-of-components.md`: recorded the tracker, candidate picker, and cancel/re-evaluation dialog responsibilities.
- `erd/homebandhu.dbml`: added v2 complaint skill/pool, offer-force, cancellation, and complaint-timer relationships.

## 2026-08-12 — Session 72: the seven migrations landed, and the complaints engine got its map

### The hosted database caught up with the repository

`PO` (the owner applied every file personally, per the standing rule). The seven pending
migrations — `20260812090000` through `20260812160000` — were applied to the hosted Supabase
project in filename order via the SQL Editor, each verified with a post-check before the next.
The migration ledger was repaired by hand (the CLI is unlinked; seven `insert … on conflict do
nothing` rows, count now 47), and the Database Advisors run came back with an empty Errors tab —
the three new tables are RLS-clean, and the 296 warnings are the linter flagging the
security-definer-RPC architecture itself plus 14 pre-existing baseline helpers, none from these
files. The original defect — `create_founder_community` tripping `communities_status_canonical`
on the legacy title-cased default — is fixed at the root.

### docs/COMPLAINT_ENGINE_STATE.md — new

`PO` (the owner asked for a detailed, teammate-facing account of everything implemented in the
complaints engine so far, frontend and backend, including the workflow, origins and assignment).
The handoff document holds the *open questions*; nothing held the *orientation* — what exists,
how a complaint moves, which endpoints and screens are wired to what. The new file carries the
lifecycle diagram, the routing and assignment rules, the full API and frontend surface tables,
and a consolidated eleven-item worklist that cross-references the handoff's argued sections.

### docs/COMPLAINT_ENGINE_HANDOFF.md — deployment caveat corrected, pointer added

`DERIVED`. §7's caveat ("no migration has ever been applied to any database") became false when
the owner applied the chain; a dated update note now says so without rewriting the sections that
relied on it. The header points newcomers at the state document first.

### docs/plans/MIGRATION_APPLY_RUNBOOK.md — the file-1 post-check anchored on call sites

`AUDIT` (found live, during the apply). The §1 post-check searched `prosrc` for the bare old
function name, which survives in the deliberate `-- CHANGED: was notify_community_staff` comment
inside the `$$…$$` body — comments in a function body are part of `prosrc`, so the check failed
on a database that was actually correct. Both patterns now match `perform public.…` call sites,
with the gotcha recorded inline.

---

## 2026-08-12 — Session 71: the portal that existed before its user did

The owner restarted their end-to-end registration test and hit it immediately: an unregistered
service professional landing at `/worker` saw the full portal — sidebar with Dashboard, Calendar,
Availability, Communities, Complaints, Messages, Profile, Settings — with the "Register as a
service partner" form rendered *inside the Dashboard tab*, and seven other tabs all clickable into
screens that are meaningless without a provider profile.

### fix(worker) — the registration gate hoisted from the page into the layout

`PO` (the owner's report, verbatim requirement: no tabs until registration is done, and the form is
not "a page in the Dashboard tab") / `DERIVED` for the mechanics — the gate itself
(`profileComplete = latitude ∧ longitude ∧ skills`) was correct but lived in `Dashboard.jsx`, a
*child* of the chrome it needed to suppress. It moved into `WorkerLayout.jsx`, which already owned
the `['worker-snapshot']` query (react-query dedupes, no second fetch): incomplete profile now
renders `RegisterProvider` full-page with no chrome mounted at all, and deep links to any
`/worker/*` sub-path redirect to `/worker` so the URL matches the screen. The predicate is
deliberately completeness, not existence — a half-saved registration still lands on the form,
prefilled. In-flight snapshot holds a neutral full-screen state so the chrome never flashes;
snapshot failure gets a minimal retry screen instead of a blank page. The old in-page gate was
deleted, not shadowed. The transition needs no reload: the form's submit already awaits the
snapshot invalidation before navigating, so the portal appears the moment registration lands.

### The pre-apply conflict sweep over the seven pending migrations

`PO` (the owner chose the full migration over a one-file unblock and asked for a conflict test
first) — a specialist ran seven static checks over the seven pending files: cross-file collisions
(none — no object is defined in more than one pending file), diffs of all 14 `create or replace`
bodies against their true last-applied predecessors (every diff is exactly the stated change; no
security-posture flip anywhere), dependency closure (zero unresolved names; file 7's independence
from files 1–6 verified), hosted-data hazards (file 5's pre-existing-violation block is
notice-only; file 7's units update can disturb nothing — no triggers, no status constraint, RLS
does not bind the SQL-editor role), backend compatibility (today's broken-by-design list enumerated;
zero signature/shape mismatches after apply; no between-file seam where the running app is worse
off mid-sequence), the static suites, and a line-level runbook audit. **Verdict: safe to apply in
filename order.** Fallout fixed on the branch:

- `test_work_order_notification_urls.py` asserted the url-repoint file is the *last* migration —
  a proxy for last-writer-wins that file 7's arrival falsified without touching the property.
  Re-pinned to the real property: sorts after `0037`/`0039` and no later file re-declares any of
  the six functions. 46/46 migration tests green.
- `DERIVED` — file 4's drop of the 6-arg `raise_complaint` discarded 0031's explicit authenticated
  grant, leaving the new 7-arg function callable only via the default PUBLIC execute privilege
  (effective callability unchanged, but convention-breaking and fragile against any future
  default-privileges revoke). The unapplied file now restates the grant on the new signature —
  explicitly no posture change, and commented as such.
- The `units_member` mechanism claim in file 7's comment and the runbook was half-wrong (that
  policy filters the *membership's* status; the unit-status filter that hides title-cased units
  lives in the baseline's belongs-to-community check) — both corrected. Runbook stale counts fixed
  (six→seven throughout; file 2 has nine function groups, not six; file 1 has two comments; file 4
  is "most DDL surface", not "only").

Recorded, not fixed (pre-existing, outside this pass): the `push_unconfigured` test fixture can't
neutralize `.env`-sourced VAPID settings, so two push-503 tests fail on any machine with keys in
`backend/.env` — flagged for its own session.

### fix(db) — community creation has been impossible on the hosted database

`AUDIT` (from the owner's live failure: admin onboarding's "Create community" step died with
*"Unable to create the association"*) — the backend log showed the real error:
`new row for relation "communities" violates check constraint "communities_status_canonical"`,
failing row containing `Active`. Root cause is a legacy seam, not this branch's work: the hosted
database predates `0001_baseline.sql`, and its legacy tooling created the status columns with
title-cased defaults. Teammate migration `20260730163759` normalized the existing communities
*rows* and added the lowercase-canonical constraint — but never fixed the column *default*, so
`create_founder_community` (which never names `status` and rides the default) has violated the
constraint on every call since that file was applied. New forward-only migration
`20260812160000_legacy_status_defaults.sql`: sets the `communities.status` default to `'active'`,
and defensively does the same for `units` **plus** the row normalization the 2026-07-30 file never
gave it — a title-cased unit fails *silently* (the baseline's unit-belongs-to-community check and
the `units_member` RLS policy both filter on `status = 'active'`, so such a unit is invisible to
resident onboarding rather than loudly rejected). On a baseline-created database every statement is
a no-op. pglast-parsed clean; independent of the other six pending files, so it can be applied
alone to unblock community creation; `MIGRATION_APPLY_RUNBOOK.md` now carries it as file 7 with
post-checks (and its trailing sections renumbered).

Five-gate: Supabase only (a column-default repair; no schema shape change, so ERD and class diagram
carry nothing new). Frontend — no change; the failing screen starts working once the file is
applied. Component design — no impact.

### fix(worker) — the chat dock was the one piece of chrome that leaked through

`PO` (owner's follow-up report: the floating chat bubble still rendered over the registration
form) / `DERIVED` — `ChatDock` is mounted once globally in `App.jsx`, outside the routes and
therefore outside any layout gate, and its only hide rule was "signed out". The dock now defers to
the same gate: on `/worker` paths it subscribes to the same `['worker-snapshot']` query (deduped,
and `enabled`-gated so admins and residents never call `/worker/snapshot`) and hides while the
snapshot is unresolved or the profile is incomplete. The predicate itself was extracted to a new
single-definition helper, `features/worker/providerProfile.js` (`isProviderProfileComplete`),
imported by both the layout and the dock so the two gates cannot drift — it lives in its own module
rather than beside `workerApi` because the tests mock that module wholesale. Deliberately NOT hidden
for membership-less identities in general: a registered-but-unhired provider keeps the dock, because
hiring conversations happen there.

Five-gate: frontend only. ERD, class diagram, component design, Supabase — no impact
(`WorkerLayout` was already the snapshot owner; this is a gate relocation, not a new component).

### Verification

`npm run test` 54 passed / 12 files (baseline 45/10; six new `WorkerLayout.test.jsx` gate tests —
no-chrome, prefill, registered-unchanged, deep-link redirect, loading hold, error retry — and three
new `ChatDock.test.jsx` tests — hidden for unregistered on `/worker`, visible for registered, and
visible on non-worker paths with zero worker-snapshot calls) · `npx oxlint` 0 · `npm run build`
clean.

---

## 2026-08-12 — Session 70: the sign-in that finally met its first real caller

The owner ran the app and OAuth completion failed with "Something went wrong" on every intent.
Live-server logs pinned it in one grep: the exchange succeeded; the very next call —
`GET /auth/session` — 500'd.

### fix(auth) — `'Profile' object has no attribute 'get'`

`AUDIT` — `_claim_staff_invitations` read the profile dict-style (`profile.get("email")`), but its
only caller has always passed the Pydantic `Profile` model — **the annotation was wrong on the day
it was written** (`5515b5d`), not broken by any merge; the initial merge-seam hypothesis did not
survive `git log -S`. The crash sat before the function's deliberate error-swallow, so every
authenticated session read died, and it stayed invisible because *no test anywhere called*
`get_session_context` — the only "callers" matching the dict annotation were the seam tests that
invented their own argument. Fixed by retyping and reading the attribute; the three seam tests now
build the real model through the repository's own mapper; new `test_api_261` drives
`get_session_context` end to end. A class audit over all of `app/` (two AST sweeps plus a manual
read of the auth path) found exactly one instance. The clean-run lesson: **a mocked test suite
proves shape agreement with its own mocks, not with the repository** — 976 tests passed around a
bug every real sign-in hit.

### The completeness check against painful-bug's history

`AUDIT` — 26 of the teammate's 28 commits were already in the branch, one more byte-identically
under a different SHA. The single true gap: `de26205` *"fix: retire preauth csrf after session
creation"* — stranded on `codex/fix-preauth-csrf` when PR #20 was closed unmerged and only its
sibling was hand-salvaged into PR #21. Verified live against HEAD (the pre-auth CSRF cookie was
never cleared after login) and **cherry-picked with authorship intact**, plus a two-line reflow to
the current lint baseline. Also noted: `origin/main` is one commit ahead (a docs-test hook by a
teammate), untouched.

### Verification

979 passed / 4 skipped (+2 from the recovered regression test, +1 from `test_api_261`) · ruff 179 ·
spec `--check` clean. The backend was restarted so the fix is live for the owner's retry.

---

## 2026-08-12 — Session 69: the coherence pass — diagrams, docs, and the apply runbook

Three specialists, one question: after Sessions 67–68, does everything still agree with everything?
Mostly yes; where not, fixed the same day. The app was also run end to end for the first time this
branch: backend healthy on :8000, frontend on :5173, and the telemetry writes returned 200 —
a real round trip into the hosted database.

### `docs/plans/MIGRATION_APPLY_RUNBOOK.md` — new

`DERIVED` — the six unapplied `20260812…` migrations verified five ways (parse, order, retry
safety, code↔schema closure over all 124 RPC call sites — zero unresolved — and the notice
handling) and turned into the owner's step-by-step apply guide. Two honest limits recorded in it:
files 1–4 have no dedicated static test suite (verified by hand for this pass), and
`complaint_department_routing`'s `raise_complaint` drop/create pair is the one transient gap a
mid-file interruption can leave.

### The diagrams — reconciled after fourteen migrations of drift

`AUDIT` — `docs/diagrams/homebandhu_submission_erd.dbml` gains the four missing tables
(`service_signup_funnel_events`, `department_skills`, `staff_invitations`,
`complaint_department_requests`) and five corrections; `erd.svg` re-rendered (determinism proved
first — the untouched source reproduced the committed SVG byte-for-byte), old render archived per
the 2026-08-10 precedent. `HomeBandhu-Architecture-Classes.puml` gains the entire
service-operations half it had never modelled and loses five methods that never existed plus the
four retired staff writes. `docs/erd/homebandhu.dbml` **did not parse at all** (`''` escapes DBML
does not have) — fixed, two tables added, and its README now says plainly it records intent, not
schema. `homebandhu-domain.puml`: the note arguing `department_skills` into non-existence replaced
with the overturn (the join was incomplete, not wrong), the three missing entities added, and the
`RequestStatus` enum `ComplaintDepartmentRequest` had referenced since Session 65 finally defined.

`AUDIT` — **the five-gate rule now names its canonical pair**: `docs/diagrams/` is what tracks the
implementation; Session 65's gate pass had updated the intent draft and the domain model while the
tracking pair drifted for fourteen migrations. Recorded here and in the orchestrator's standing
notes so the next gate pass checks the right files.

### The documentation cross-check

`AUDIT` — one real deviation: `api_yaml_mapper.md` was 94 rows stale against Session 68's final
docs commit — every diff a line number, none a route. Regenerated; the lesson is that a docs-only
last commit still needs a mapper regen. All 20 `api_map_scan` findings re-verified as recorded
verdicts (none new across +20/−4 operations); all 24 user-story verdicts agree across the index,
§16 and the spec; zero dead anchors across eight documents. Stale prose fixed in eight files —
API.md's banner and §16.6 (rebuilt, four groups had gone missing), the wiring audit, the agenda
(item 17 closed, item 12 three-quarters closed), `DECISIONS_NEEDED` (B14, B15, B17 closed, B12
part), both build plans, and the handoff's two "has no caller" notes (both now have callers; the
fork stays the owner's). Dated finding-blocks were left as records, per convention.

### The server

`AUDIT` — `.claude/launch.json`'s backend entry used `sh`, which does not spawn on this machine —
now PowerShell. `/health` answers ok; the signed-out 401 pair is the session probe working as
designed; a stray 773 KB `nul` redirect artifact was removed from the repo root.

---

## 2026-08-12 — Session 68: phase 7, the symmetry ruling, and the end of the orphan list

Six specialist assignments (three new charters, three follow-ups to standing agents), same
orchestration as Session 67. The API now serves **195 operations** and the sweep reaches **186** —
the 9 remainder are all structurally-invisible or declared paths, so **potential issue 10's orphan
inventory is empty**.

### The PO rulings this session

`PO` — **issue 16 is ruled**: *registered professionals are assumed not to be living in any
association.* The separate-account rule is identity separation, the "plumber who lives here" case
is two accounts, and `20260812113000_professional_membership_symmetry.sql` enforces the missing
direction (`HBSEP` → 409 `professional_account_separate`, raised by the membership trigger, checked
at every membership writer including four in applied files). Consequences: `POST /access-requests`
refuses a professional at request time; approval failures stopped masquerading as
`access_request_not_pending`; a professional's invite claim gets a real 409 instead of a 500; and a
professional provisioned as a manager by email silently fails to claim —
`STAFF_PROVISIONING_DESIGN.md` records that as the ruled behaviour and its cost.

`PO` — *"proceed with step 7 after any fixes remaining and fixable"* — the audit's approved-fix
list was implemented before/alongside the wiring, per Session 67's escalations.

### Phase 7 — 26 operations wired, 4 retired

`DERIVED` — **work orders (8)**: a triage surface at
`/{portal}/departments/:departmentId/work-orders`, all three portals, hiring-precedent shape. Two
lifecycle questions went to `COMPLAINT_ENGINE_HANDOFF.md` §10 rather than being decided — the §8
assignment fork (now purely semantic, both options built) and whether work may be raised against a
terminal complaint.

`DERIVED` — **amenities (10 + reports)**: the admin booking/approvals/ledger/reports screens read
the API; 14 demo functions and 4 modules deleted with their last readers. A live bug died with
them — the demo posted the *occurrence* id to `…/{seriesId}/approve` (agenda item 16 closed by the
same change). The **Edit Booking modal was removed**: no update-booking endpoint exists (API.md §15
now says so). The resident "Your Bookings" 403 is fixed; the slot-picker 403 beside it is recorded
in issue 09 as unfixable-by-wiring (no availability read exists, by design).

`DERIVED` — **money (3) + `POST /admins` (1)**: billing settings became a real read/edit (the
screen had been hard-coding ₹4250/₹100 into every save); invoice issue + offline-payment recording
landed with bookkeeping-not-checkout framing; "Add admin" became "Promote to Admin", which is what
the endpoint does.

`AUDIT` — **the four `departments…/staff` writes are retired**, on a per-operation evidence table:
every one superseded by the `0035` hiring flow before it ever gained a caller. Striking the dead
`staff: []` payload from the admin form also fixed a live defect — key-presence means *replace*,
so **every department edit had been silently deactivating its whole roster**. Spec 199 → 195.

### The notification links

`AUDIT` — `20260812120000_work_order_notification_urls.sql` repoints the seven `?job=` emissions
(`0037`×4, `0039`×3) at the triage screen; `portalUrl.js` learned `work-orders` as a department
sub-screen. Fixing it exposed **three latent holes in `test_notification_links.py`** — bare
`<Route>` fragments parsed to the root, urls read only to their first line, and no model of
forward-only supersession (permanent now, not incidental) — all three fixed, and the repaired
checker surfaced a **new** dead parameter: `?departure=` to `EmployeeDetail.jsx` (`0045`×2), on
record in issue 12.

### Docs

`DERIVED` — API.md: the four staff-write sections replaced by a retirement record; the §15 "no
migration has ever been applied" claim expired against the boundary; the missing update-booking
endpoint recorded; `residentId`'s dead `GET /residents` citation corrected; the `HBSEP` 409
documented on its three surfaces. Issues 9 (amended), 10 (emptied), 12 (item 4 closed, successor
named), 16 (resolved) updated with the migrations README, the meeting agenda, the wiring audit,
`DECISIONS_NEEDED` (resident Pay affordance) and both design docs.

### Verification

976 backend tests / 4 skipped · ruff 179 · spec 195 ops `--check` clean · mapper clean · scan 20/20
documented · build clean · 45 vitest · **oxlint 0** · sweep 186/195, zero genuine orphans. The six
`20260812…` migrations are pglast-parsed and **unapplied**; issue 4 tracks them.

---

## 2026-08-12 — Session 67: the audit of the merged commits, and phase 6 by specialists

The first session run by the charter workflow: three sub-agents (charters in `.claude/agents/`),
each with a scope fence and a mandated report, with synthesis and every `docs/` change staying here.
Two things happened at once: the merged service-professional commits (`fc69d3f`, `ce3fafe`) were
line-audited on the user's suspicion of bugs, and the resident portal was wired end to end
(phase 6 — potential issue 09 resolved, see its banner).

### The audit: twelve findings, four fixed, two escalated, six recorded

`AUDIT` — the audit also *cleared* the merged work's foundations, which is worth as much as the
findings: PostGIS units and argument order correct, SECURITY DEFINER hygiene complete, registration
atomic, the RLS-recursion fix genuine and strictly narrower than the policy it replaced, and
`ce3fafe`'s rewrites of the applied files byte-faithful to the baseline.

**Fixed the same day** (each with a fail-before/pass-after test): the email-confirmation
`intent` concatenation that would have broken confirmation outright under a `{{ .RedirectTo }}`
template; the `/get-started` dead end for an email-path service professional (third door, destination
computed from `destinationAfterAuth` so the two paths cannot drift); the admin Settings coordinate
inputs whose `required`/`min`/`max` never fired outside a form; the telemetry visitor cookie whose
30-day window never slid, double-counting returning visitors.

**Escalated to files of their own**: [potential issue 15](potential%20issues/15-the-service-professional-intent-dies-in-the-confirmation-email.md)
(the intent still dies in the fixed email template, so the funnel's `auth_completed` undercounts —
a dashboard-configuration decision) and [16](potential%20issues/16-the-separate-account-rule-only-looks-one-way.md)
(the separate-account rule is enforced in one direction only — a product question).

**Recorded here, deliberately not acted on**: the unauthenticated telemetry endpoint joins
potential issue 3's rate-limiting table; `sign_in_with_password`'s unconditional confirmed-email
check now applies in production only (staging strictness is a conscious choice for the owner);
`service_applications_read` silently lost department-less managers (inert — nothing mints one);
`departments.hours` landed as `text` against the baseline's `jsonb` (inert type drift, now
permanent); `0034`'s `search_serviceable_communities` comment describes the pre-replacement
null-coordinate behaviour; CI's closing `git diff --check` cannot catch generated-file drift, and
the workflow exports the (demo) service-role key to `$GITHUB_ENV` — both left because CI cannot be
verified locally.

### `docs/potential issues/`

`AUDIT` — 09 resolved (banner carries the residual: the Amenities "Your Bookings" table, now
phase 7's first item). 10 recounted: 164/199, with `GET /events` moved to "reached another way"
(`EventSource`, structurally invisible to the sweep). 3 gained the telemetry endpoint. 4
half-resolved by the boundary — `0001`–`0047` applied, the four `20260812…` files still nowhere.
15 and 16 are new.

### `docs/API.md`, router docstrings, `docs/FRONTEND_WIRING_AUDIT.md`

`DERIVED` — the two "the form collects them [attachments]" sentences now record that it no longer
does; the wiring audit's resident postscript records phase 6 and that `payInvoice` was wired to the
resident simulator, not the forbidden admin settlement endpoint.

### One frozen-interface lesson

`AUDIT` — `residentApi.js` was written by the orchestrator as the frozen interface before launch,
and both of its documentation errors (`resolveComplaint`'s invented `{accepted}` shape; `body` where
`AddCommentRequest` says `message`) were caught by the implementing agents against the schemas.
The convention held — both agents reported rather than silently diverging — but the lesson stands:
an interface frozen before its shapes are verified freezes the errors too.

---

## 2026-08-12 — Session 66: the deployment boundary, and what it invalidated

A teammate's branch landed two commits, and one of them moved a rule this workstream had been
building on for six weeks. **The linked hosted Supabase project was verified on 2026-08-11 with
every repository migration through `0047` applied.** Those files are immutable from now on, and
corrections to them are forward-only.

Session 65, immediately below, was written hours earlier and is **wrong in three places as a
result**. It is left standing because it is an accurate record of decisions taken under the rule of
that day; each correction is named here rather than by editing the entry.

### `backend/supabase/migrations/README.md`

`AUDIT` — **the number ranges are closed at `0047`.** Everything after the boundary is a timestamp.
This overturns Session 65's `0050`–`0059` extension, which was correct when written and is now moot:
numbers exist so two people do not pick the same next integer, and a timestamp cannot collide. The
table is kept because it explains files that already exist. New rows for the seven files after the
boundary.

`AUDIT` — the `0040` **corrected 2026-08-12** row is withdrawn. That correction now lives in
`20260812090000_notification_audiences.sql`. The row points there instead.

### Migrations — three renamed, two written, three reverted

`DERIVED` — `0048`/`0049`/`0050` became `20260812090100_skills_and_categories.sql`,
`20260812090200_staff_provisioning.sql` and `20260812090300_complaint_department_routing.sql`.
Not cosmetic: `0048` sorts **before** `20260811162409`, so leaving the numbers would have run this
workstream's files before the ones already written against them.

`DERIVED` — `20260812090000_notification_audiences.sql` is new, and exists only because of the
boundary. Session 65 corrected `0033`'s amenity audience and `0040`'s incident audience *in place*;
both files are applied, so both edits are reverted and both functions are repeated in full in the
new file. Same for the three complaint notifications Session 65 edited into `0031` — they are now
section 10 of the routing migration.

> **What the boundary costs, stated plainly.** The old README allowed in-place correction
> specifically so that changing one string inside a function body would not require re-declaring the
> whole function, *because the copy is then free to drift from the original*. That reasoning was
> right and the allowance is gone, so the drift risk is now real and permanent. What is done about
> it: every copied body was extracted mechanically from the applied file, so the starting point is
> provably the applied text, and every difference carries a `-- CHANGED` marker at the line it
> changes.

`AUDIT` — **`search_hireable_service_providers` was about to be silently reverted.** Both this
workstream and `20260811162409` redefine it with the same signature, so `create or replace` is
last-writer-wins and the renamed file now runs second. Left alone it would have withdrawn five
things that have nothing to do with skills: the radius bound and its GiST-prunable outer bound, the
`is_available` / `location is not null` filters, the worker/security mode exclusion, the
deterministic ordering, and `can_hire_for_department` in place of `can_manage_department`. The
department-skills union is now rebased onto that file's body as a one-CTE diff.

### `docs/API.md`, `docs/COMPLAINT_ENGINE_HANDOFF.md`, `docs/potential issues/14`

`AUDIT` — every sentence claiming *no migration in this project has ever been applied* is now false
and is corrected with the date the claim expired. Three in API.md, one in the handoff, one in issue
14, one in `test_dispatcher.py`, one in `test_complaint_routing.py`.

### `docs/API.md` — `GET /departments/{departmentId}` gains `canHire`

`DERIVED` — the hiring authority moved and is **not** overturned here:
`can_hire_for_department` gives hiring to the department's own active manager, by membership role or
by roster rank, with community admins as the fallback *only while it has neither*. That is the other
workstream's decision.

What follows from it is ours. **The question stopped having a role-shaped answer** — the same admin
may hire for one department and not the next — and both frontend gates were still asking it
role-shaped, in opposite directions: a security department's roster manager holds
`membership_role = 'security'` and was hidden from a permission they hold (`docs/potential issues/14`
exactly, recreated), while an admin on a managed department got an empty applications list and an
`HB403` candidate search, which reads as a broken screen rather than a restricted one.

So the department read carries the answer, computed by calling that function, and the screen says who
decides. `usePortalScope.canHire` is deleted rather than corrected: no value of that shape can be
right, and it had no callers.

`null` on the list is *not asked*, distinct from *no* — it is one round trip per department and the
list has no control that needs it.

---

## 2026-08-12 — Session 65: three open questions, answered

> **Corrected by Session 66, above.** The migration-range extension, the `0040` in-place row, and
> the reasoning that made both available were overtaken by the deployment boundary the same day.

Session 64 closed with four open questions. Three were put back to the product owner and answered;
the fourth — complaint **assignment** semantics — stays with the complaint-engine owner and was not
touched.

### `backend/supabase/migrations/README.md`

`PO` — the service-operations range is extended to **`0050`–`0059`**. `0049` took the last number in
`0034`–`0049` and complaint routing still needed a file. Nothing claims `0050`+, and the rule *lowest
free number in your own range* only works if a range that runs out gets extended rather than quietly
borrowing from a neighbour. Recorded with the note that extending grows the table at the end, never
in the middle.

`AUDIT` — `0040` gains a **corrected 2026-08-12** row, following the precedent `0022`, `0032`,
`0036`, `0037` and `0043` set: nothing here has been applied to any database, so an audience mistake
inside a function body is fixed in place. **This stops being available the moment anything is
applied**, and the README already says so.

### `docs/design/STAFF_PROVISIONING_DESIGN.md`

`PO` — the single factor **stands**, and a claim code was offered and declined: *"lets assume that
the admin wont make any typos for now and if the admin wants he can change the email when he notices
via an edit option."* The recovery path was built instead —
`PATCH /departments/{id}/staff-invitations/{invitationId}`.

`DERIVED` — the **department is not editable** on that endpoint. It is what `can_manage_department`
authorizes the call against, so a move would let the manager of one department mint staff into
another. Moving an invitation is revoke-and-reissue under the authority of wherever it is going.

The trade-off section now says plainly what the edit does and does not change: it makes the
*accident* recoverable and does nothing about the security case. An address that is wrong *and*
belongs to a real HomeBandhu user still admits that person, still silently.

### `docs/erd/homebandhu.dbml`

`AUDIT` — **`complaints.department_id` was already in the ERD and had no implementation.** Routing
happened only when dispatch built a work order, so before that moment a complaint belonged to nobody.
`0050` brings the implementation into line with a design decision already recorded here rather than
changing the design.

`DERIVED` — new table **`complaint_department_requests`**, the only genuinely new entity. A
supervisor cannot move a complaint themselves, so the request is a row rather than an UPDATE: one who
could push work out of their own department could empty it, and the receiving department would have
no say either way.

### `docs/class-diagram/homebandhu-domain.puml`

`DERIVED` — `Complaint` gains `departmentId [0..1]` and `routeToDepartment(...)`, plus the
`ComplaintDepartmentRequest` entity and five associations. **Null `departmentId` is a real state, not
a gap** — it means the rule found nothing and the complaint is in the administrator's triage queue.

### `docs/API.md`

`PO` — new **§7.1**, the routing rule in precedence order: category, then the resident's own guess,
then the triage queue. Category over the resident's pick is the ruling and it is the right way round —
the category mapping is curated by somebody who knows how the society is organised, and the resident
is guessing.

`DERIVED` — **`"Other"` and `"Not sure"` are documented as *not* special values.** They are the two
inputs that match nothing and fall through. Naming them as sentinels would have put two more strings
in the system to express what the absence of a match already says.

`DERIVED` — an **ambiguous category routes to nothing**. `department_categories` has a composite
primary key, so one category may belong to several departments; the rule refuses to pick even when
the resident named one of the candidates, because letting them break the tie would invert the
precedence rule the section exists to state.

`AUDIT` — the complaints preamble's audience claim was **wrong and is corrected**: raising,
reopening, confirming and commenting reached every admin *and every manager in the community*, not
"admins and managers" of anything relevant. Four notifications now go to the admins and the
complaint's own department manager.

### `docs/potential issues/14-…`

`AUDIT` — the three notification links this file recorded as deliberately-unrewritable are all
closed, and **none by adding a rewrite rule**. Two were audience mistakes (`0033`, `0040`) and one
was a missing column (`0050`). The lesson is written down: *a link with no good destination is often
a notification with no good recipient.*

### `docs/COMPLAINT_ENGINE_HANDOFF.md`

`PO` — new **§9**, written to be read *before* the owner concludes their §8 fork was decided for
them. It was not: §8 is which **person** works a complaint, §9 is which **department** owns it, and
`0050` deliberately answers only the second — it writes no `assigned_to_membership_id` and creates no
work order. One genuine judgement call is handed over: whether a transfer should need consent from
the *receiving* department, which today finds out by being notified after the fact.

---

## 2026-08-11 — Session 64: the manager who could not hire

A follow-up to Session 63, on one instruction: build out the hiring screen recorded as
`docs/potential issues/14`, and first **report which role it had actually been built for**.

### `docs/potential issues/14-…` and its `README.md`

`AUDIT` — marked **resolved**, and rewritten rather than annotated, because the audit found the gap
was wider than the file described. The answer to "was this built for the admin or the supervisor?" is
**the admin**, and never the supervisor: `require_admin_or_manager` checks the *membership role*, and
a supervisor holds `worker`. Rank and role are separate axes and only role is checked here, so
supervisors have never had hiring permission at any layer.

Two things the file did not know when it was written, both now recorded in it: the
**security-department manager** had the identical gap (`SecurityLayout.jsx` said so in a comment),
and the `service_application_received` notification — which `0035` addresses to
`array['admin','manager']` — carried an `/admin/…` link that silently redirected a manager to their
own overview.

### `docs/API.md`

`DERIVED` — a new `GET /api/v1/service-providers/{providerId}`, documented with the reason it is
narrower than the provider's own profile read: no coordinates and no profile id, because
`distanceKm` from the candidate list already answers where somebody is and a home coordinate is a
different fact offered for a different purpose. The **guard** is the point of the route existing at
all — `service_providers_read` is `auth.uid() is not null`, so Postgres would give the row to any
signed-in caller.

`PO` — `rank` and `shift` struck from `POST /departments/{id}/invitations` and
`POST .../decide`, quoting the ruling verbatim in place. Both halves recorded separately because
they are separate facts: leadership never comes from the hiring path (it is provisioned by email),
and `staff_assignments.shift` is a column **nothing schedules from** — the dispatch sweep and
`security_shifts` do that work. `security_shifts` is explicitly untouched, so nobody reads "there is
no shift system" as applying to the gate rota.

### `docs/changelogs/2026-08-11-…`

`DERIVED` — a phase-6 section, two new breaking-change entries (7 and 8), and the open-questions
section rewritten into **settled** and **still open**. Two of the three questions raised at the end
of Session 63 were answered by the PO and are now recorded as decisions with their reasons, not as
questions.

### Not changed, deliberately

The ERD and class diagram. Session 64 adds **no tables, no columns and no migration** — the
`0034`–`0049` range is exhausted and this work needed none of it, because
`service_provider_overview` was already readable and `decide_service_application` already defaulted
an omitted rank to `member`. A five-gate pass with nothing to record is worth saying out loud rather
than leaving as a silent omission.

---

## 2026-08-11 — Session 63: departments, skills and the manager who could not sign in

Four instructions, and the first three are done. The fourth — wire every dangling backend operation
— is deliberately incomplete and says so at the end.

### `docs/changelogs/` (new folder)

`PO` — the ruling was to keep a **detailed changelog of this execution, in addition to the normal
ones, so it can be shared with teammates**. `CHANGE_LOG.md` is keyed on documents and is terse;
that one is keyed on endpoints, schema and contracts, and carries a "files touched, grouped by
owner" section so each person finds their own. `docs/changelogs/README.md` gives the folder a
convention rather than one example, the shape `docs/issue fixes/` was given.

Written **per phase as each landed**, not at the end. A changelog assembled from memory after eight
phases is a summary, and the details a teammate needs are exactly the ones that get lost.

### `docs/API.md`

`DERIVED` — six operations for the skill catalogue (`0048`) and three for leadership provisioning
(`0049`), each with its status table. `GET /skills` gained `q`/`limit` and the entry now states that
the no-query behaviour is unchanged, because it already had a consumer.

`DERIVED` — the `GET /departments/{id}` entry changed from `ADMIN` to `ADMIN` **or the department's
own manager**, with the reason: the manager portal has no other way to read its own department, and
this was the only department operation with no frontend caller at all.

`PO` — a new §"Leadership provisioning" recording the ruling verbatim: *managers and supervisors
have no registration process; servicemen are the only role in the service section that does.*

### `docs/design/STAFF_PROVISIONING_DESIGN.md` (new)

`DERIVED` — required, not optional: `0049` changes `auth_service.py`, which belongs to the auth
workstream, and the standing rule is that file is only touched with a design doc. It records the
mechanism, the derived-role table, and **the one-factor trade-off in plain words** — whoever holds
that mailbox at first sign-in becomes the manager. The resident invite's mandatory token is
untouched; leadership got its own table specifically so that rule would not have to bend.

### `docs/FRONTEND_WIRING_AUDIT.md`

`AUDIT` — the `GET /complaint-categories` row is struck through and marked reinstated. Its
retirement reason was a statement about two screens, and **both halves expired**:
`CreateDepartment.jsx` was deleted in `38927e5`, and the department form's category field is now a
combobox that cannot prevent duplicates without the list. The reinstated read also is not the
retired one — it carries each category's linked skill.

### `docs/COMPLAINT_ENGINE_HANDOFF.md`

`DERIVED` — a new §8. The "Assign technician" dropdown had been reading `department.staff`, which
the snapshot always builds empty, so it has been offering a choice of nobody. It now reads the real
roster. **The question of what an assignment *means* is left open on purpose** — three possible
shapes are set out, and the choice belongs to whoever owns the complaint lifecycle.

### `docs/potential issues/14` (new)

`AUDIT` — a department manager may hire and has no screen to hire from. Reusing the admin hiring
screen would have shipped four `/admin/...` links that 403 for them, so the tab was dropped and the
gap written down. Also notes something about the sweep itself: **reachability is not the same as
reachability by everyone who is allowed.**

### Two corrections to earlier sessions

> **`0035` said it replaced `department_overview` and did not.** Its own header states the reason
> to: *"leave `department_overview` matching on `'head'` and the admin screen's head field is
> permanently null."* It replaced `apply_department_head` and never touched the view — so
> `head_name` has been null for every department in the API since `0035`. `0048` corrects the
> predicate while replacing the view anyway. Recorded here rather than only in the migration,
> because a comment claiming a fix that was not made is worse than no comment.

> **Session 60's five-gate note on `search_hireable_service_providers` is now partly superseded.**
> The function derives the skills a department needs from its categories; from `0048` it is the
> union of that and the department's own skills. Not a correction of that session — a deliberate
> behaviour change, made because otherwise attaching a skill to a department would change nothing
> anybody could observe.

### What is not done

`PO` — the ruling on the connectivity sweep was **"everything dangling"**, all 51 operations.
Phases 1–5 (skills, provisioning, the admin form, the manager portal) are complete; **phases 6 and 7
— the resident portal's 24 operations and the work-order, amenity and money surfaces — are not
started.** The plan named them as the cut line if scope ran long, and it has. They are unblocked and
independent of everything above.


## 2026-08-11 — Session 62: the four that are not ours, and everything nothing reaches

**Context.** PO: *"are the 5 issues you identified documented? if not document them in potential
issues. fix all other issues that we have identified and after that do a full sweep for dead or stale
stuff."*

**They were not documented — they were recorded in a test constant, which is not the same thing
(`AUDIT`).** `IGNORED_QUERY_PARAMETERS` kept the list honest but told nobody outside the suite what
each entry cost a user or who could fix it. A finding whose only home is an assertion is findable by
people already reading that file.

### `docs/potential issues/12-notification-parameters-no-screen-reads.md` — new (`PO`)

Thirty-six notification `url` values across seven migrations carry a query parameter, in ten distinct
`(path, parameter)` pairs. The file gives each open one its emitting migration lines, its emission
count, the screen, the owner, and what a fix would actually be — deliberately not batched, because
the four need four different answers. `/resident/complaints?complaint=` is eleven of the twenty-three
open emissions and the *least* fixable: the screen behind it reads a zustand demo store, so honouring
the parameter would highlight a seeded row unrelated to the complaint. It closes when issue 9 closes.
`/admin/departments?job=` has nothing to fix at all — there is no supervisor triage screen, so the
parameter has no reader rather than the wrong one.

### `frontend/src/pages/WorkerDashboard/Messages.jsx` — `?conversation=` is honoured (`DERIVED`)

**The fifth pair was ours, which Session 61 got wrong** and this corrects. `0041:611` notifies the
provider with `/worker/messages?conversation=<id>`; the screen kept the open thread in `useState`,
which cannot be linked to, so the bell landed the worker on a thread list with nothing opened. The
admin twin (`AdminDashboard/Messages.jsx`) got this right the day it was written and says why in its
header — this side simply never had it.

Selection moved to `useSearchParams`, and opening a thread is a real history entry on purpose: on the
phone this screen is built for, that makes the hardware back button close the thread rather than
leave the portal. An **error branch** came with it, because the id can now arrive from a link: a
closed thread, or one belonging to another account, previously rendered as a blank thread under a
real header, which reads as *no messages* rather than as an error.

### `backend/scripts/dead_code_sweep.py` — new (`PO`, *"a full sweep for dead or stale stuff"*)

Four questions nothing in this project asked: frontend modules nothing imports, frontend exports
nothing outside the file mentions, backend module-level names that occur exactly once, and relative
Markdown links in `docs/` that resolve to nothing. None is an error in either language, and a
Markdown link is checked by nothing at all. Two dead-code sweeps had been done here by hand; this is
the same work, repeatable, with its blind spots in the docstring rather than in someone's head —
decorated functions are excluded (a route handler is reached through `@router.get`), the export check
is a word search so it under-reports rather than accusing live code, and a name whose only caller is
itself dead still counts as live.

**Deleted, ours:** `security_service.export_datasets()` (no caller — `export_csv` consults `_DATASETS`
directly), `vocabulary.js`'s `SHIFT_STATUSES` and `startOfToday()`, and the unnecessary `export` on
`offlineGate.js`'s two storage keys and batch size, which are module-private on purpose: the
functions beside them are what keeps a half-written value from reaching a caller.

### `docs/potential issues/13-dead-code-in-files-this-workstream-does-not-own.md` — new (`AUDIT`)

The rest of the sweep's output, recorded rather than changed: three backend names with zero
references (`require_active_role`, `WithdrawAccessRequest`, and the three cookie constants superseded
by `cookie_name()`), two orphan frontend modules, eight unused exports — **all three of `phone.js`'s,
which is the shape of a module left behind by the phone/OTP design** — and `graphify-out/`, 57 tracked
files and 2.6 MB of a code-graph tool's output that nothing refers to.

`require_active_role` is flagged for a second look rather than a straight delete: issue 2 kept `Role`
in `roles.py` *on the grounds that this file imports it*, so if the function goes, that reason goes
with it.

### Stale claims corrected (`AUDIT`)

- **Issue 4** said the migration directory held 22 files, `0001` through `0032`. It holds **37**.
  Fifteen landed since it was written and every one is unapplied too, so the finding did not change —
  only its size did, which is the argument for the finding.
- **Four dangling relative links**, all to files deleted in the change that made the document true:
  `ADMIN_REGISTRATION_FLOW.md`'s OTP page and `AuthFlowRoute.jsx`, and `FRONTEND_MEETING_AGENDA.md`
  items 8 and 9. The agenda items keep their text and gain dated notes — item 9 is **resolved** (one
  department-create path now, not two) and item 8 is **overtaken but not resolved**, because the
  question of whether `flat` holds a bare number or a full code is still open even though the second
  code path is gone. Item 9's third disagreement is explicitly *not* resolved: department categories
  are claimed by name against no closed list, so `Others` is still claimable and still carried by no
  complaint.
- **`API.md` §16.4, US-2.1** carried an unmarked stale table row — *"any write endpoint: missing"* —
  two paragraphs below an endpoint table listing four visitor-pass writes `0032` shipped. Found while
  answering *"are there any user stories left to be fulfilled"*, which is the use this section is
  for. The section deliberately keeps superseded layers, so the row is struck through and the
  correction stated above it rather than the layer being rewritten: US-2.1's remaining gap is the
  *question* side, not the write side — nothing raises `visitor.approvalRequested` because a
  guard-raised approval request has no endpoint. An unmarked stale row inside a document that marks
  all its other corrections reads as current, which is worse than no record.

**Baselines now:** **860 tests** (unmoved — the parameter inventory asserts four instead of five),
ruff **153**, oxlint **7**, map-scan **20**, spec unmoved at 150 paths / 179 operations, mapper
`--check` clean, `npm run build` and all three node suites clean. `dead_code_sweep.py` reports **zero**
dangling links and nothing of ours.

---

## 2026-08-11 — Session 61: the notification parameter, not just the path

**Context.** PO: *"fix the gap about the shifts screen. plan and execute."* The gap is the one
Session 60 declared on itself — `0043`'s `security_shift.assigned` was corrected to
`/security/shifts?shift=<id>` and the screen it lands on never read `shift`.

**Why this is a defect and not a polish item (`DERIVED`).** It is the same failure as the wrong path,
one step later: the link works, so nothing reports it. The guard taps *"A shift was handed to you"*,
arrives at a fortnight of roster rows, and has to find theirs by eye. Session 60's own words for the
path defect apply unchanged — *no error anywhere: not in the browser console, not in the API log, not
in a test run.*

### `docs/API.md` §19 — `GET /security/shifts` gains a `shiftId` filter (`DERIVED`)

Not a highlight-only fix, because **the linked shift is often not on screen to highlight.** A handover
is driven by `0045`'s *scheduled* departure, whose date can be weeks out, and the screen queries ±7
days. Widening the window is worse than useless: the list caps at 200 rows ordered by start, so a
wider range on a multi-post gate can truncate away the row being looked for. One id, one row, no
window.

**A filter and deliberately not `GET /security/shifts/{id}`.** The worker precedent that shape would
copy (`GET /worker/jobs/{id}`) exists because it returns a *richer* model — the resident's name, flat
and the complaint in full. There is no richer shift model, so a second path would serve the same
`SecurityShift` and cost an operation, moving the `179 operations / 150 paths` figures in five
documents to express *the same list, narrowed to one* — which is what the `postId` filter beside it
already does. An unknown id answers `200 []`, **not `404`**, so the read cannot be used to test
whether a shift exists in a community the caller cannot see.

### `docs/design/SECURITY_PORTAL_DESIGN.md` — new *"The parameter, not just the path"* (`AUDIT`)

That file previously recorded the deliberate limit: *"the test deliberately ignores query strings,
because an ignored parameter is a missing feature and an unroutable path is a broken link."* Right
about the path check, wrong as a stopping point. The section now describes both halves and links the
five that remain to their owners.

**`backend/tests/test_notification_links.py` turns the blind spot into an inventory.** It resolves
each notification path to the component `App.jsx` mounts there and asserts the set of `(path,
parameter)` pairs no screen reads **by equality** against a named constant. Equality rather than a
subset, so the record cannot decay into an allow-list nobody prunes: a screen that starts honouring
its parameter has to leave the list in a diff somebody reviews.

Six pairs were ignored; five remain, and none is this workstream's to fix — `/resident/complaints`
and `/admin/complaints` (issue 09 and `COMPLAINT_ENGINE_HANDOFF.md`), `/admin/departments?job=`
(issue 10 — no supervisor triage screen exists, so there is no parameter to read yet),
`/admin/amenities?booking=` and `/worker/messages?conversation=`.

> **Corrected the next session.** *"None is this workstream's to fix"* was wrong about one of the
> five: `/worker/messages?conversation=` is our own screen, from Step 8 of the same phase. Fixed in
> Session 62 below. The claim was made from the ownership of the *screens the other four land on*
> without checking the fifth, which is the same shortcut — writing from memory of the code rather
> than from the code — that the link test exists to catch.

**Baselines now:** **860 tests** (856 + 2 shift filter + 2 parameter inventory), ruff **153**, oxlint
7, map-scan 20, **spec unmoved at 150 paths / 179 operations**, mapper regenerated (21 rows, all line
numbers), `npm run build` and all three node suites clean.

---

## 2026-08-11 — Session 60: the compatibility sweep, two fixes and three filed issues

**Context.** The PO asked for an end-to-end compatibility check — *"from auth to resident to admin to
all service people"* — then ruled on its output: *"lets fix findings 1 and 2 … go into detail about
each and every other finding and store them as separate files."*

The sweep compared 124 frontend call sites against the 179 live operations, every notification `url`
against the route table, and the portal-derivation chain end to end. **The call layer is clean**: no
path or method mismatch anywhere. Both real defects were one layer up, in reachability.

### `docs/design/AUTH_AND_SESSION_DESIGN.md` — new §5.6, and §5 loses its count (`AUDIT`)

`/security-manager` was reachable by **no user the system can create**. Session 57's §5.3 narrowed the
portal predicate from *"a manager with a department"* to *"a manager whose department is a security
department"* — the right narrowing of the wrong question, because `hire_service_applicant`
(`0035:918`) is the only minter of a department membership and it writes `security` or `worker`.
Nothing writes `manager`.

The answer was already in the repository, in SQL, with a comment saying so: `gate_admin_community_for`
(`0040:589`) has defined a security manager as a `security` membership with an active roster rank of
`manager` or `supervisor` since the day it was written, under the heading *"D3 made rank and role
separate axes."* `_portal_for` now asks that question, so the portal and the live authorization agree
by construction — the alternative being a portal that is either unreachable or full of screens whose
writes 403. `supervisor` is admitted because that predicate admits it.

This orphaned four pages, `GET /security/roster` and migration `0047` — all built the previous day.
`/security/*` also now admits `SecurityManager`, without which the fix would have started bouncing
newly-senior guards off the target of two shift notifications.

### `docs/design/SECURITY_PORTAL_DESIGN.md` — the deep-link table gains two rows and a correction (`AUDIT`)

That file already said *"a notification whose `url` 404s is a defect that no test catches"*. Four of
them were, addressed to people whose portal has no such route:

| Migration | Was | Recipient | Now |
|---|---|---|---|
| `0032` `decide_visitor_pass` | `/security/visitors?pass=` | the gate | `/security` |
| `0036` ×3 | `/worker/jobs/<id>` | the worker | `/worker?job=<id>` |
| `0037` ×2 | `/worker/jobs?job=<id>` | the worker | `/worker?job=<id>` |
| `0043` `reassign_departure_item` | `/security-manager/shifts?shift=` | **the guard handed the shift** | `/security/shifts?shift=` |

The last is the sharpest: a manager's prefix on a notification addressed to a guard. It is no longer
asked for but checked — `backend/tests/test_notification_links.py` parses `App.jsx`'s nested route
tree and asserts every `url` literal in every migration resolves against it, with four cases pinning
that the matcher still rejects the historical values, because a link checker that cannot fail is
worth nothing.

**The migrations were corrected in place rather than superseded (`DERIVED`).** Seven string literals
sit inside seven functions of ~600 lines total, each defined exactly once; a fix migration would
re-declare all seven to change seven strings, and the copies would drift. `0022` set that precedent
on 2026-08-04. `backend/supabase/migrations/README.md` now states the rule and its expiry: once
anything has been applied anywhere, this stops being available.

### `docs/API.md` §3.5 — `portal` becomes a documented closed list (`DERIVED`)

Six values, who gets each, and the two spellings of `security-manager`. `portal` is what the frontend
routes on and it had never been written down anywhere a client could read it — which is part of why
one of its values could be unsatisfiable for a day without anyone noticing.

### `docs/potential issues/` — becomes an index plus three files (`PO`)

The three findings not fixed are now one file each, per the ruling, each naming the contract it says
is wrong and linking to it:

| File | Finding |
|---|---|
| [`09-resident-portal-is-still-a-demo.md`](potential%20issues/09-resident-portal-is-still-a-demo.md) | seven of eight resident pages read the zustand demo store; 24 endpoints built for them have never been called |
| [`10-api-operations-with-no-frontend-consumer.md`](potential%20issues/10-api-operations-with-no-frontend-consumer.md) | 51 of 179 operations have no caller, sorted into what that means — including the supervisor triage surface, the manual half of the dispatch engine |
| [`11-snake-case-in-the-published-contract.md`](potential%20issues/11-snake-case-in-the-published-contract.md) | §1.3's *"everything else: camelCase"* is false for 28 properties across three non-auth surfaces. **The code is consistent and the document is wrong**, which widens issue 8 from one seam to five |

`README.md` becomes the index for all eleven, with issue 6's count recounted (149 → 153) and issue 8
marked superseded in scope.

**The sweep ships as `backend/scripts/frontend_api_sweep.py`**, so those documents' *How to confirm*
step is a command rather than a claim. It declares its own blind spot — one call site whose first
argument is an expression — rather than letting it inflate the unreached list.

**Baselines now:** **856 tests** (843 + 7 portal + 6 link), ruff **153**, oxlint 7, map-scan 20, spec
and mapper both up to date, `npm run build` and all three node suites clean.

---

## 2026-08-11 — Session 59: §3 of the mapper becomes generated, and finds a bug in the scanner

**Context.** Session 58 raised the mapper's drifted `API.md:NNNN` references and declined to fix
them by hand, on the grounds that *"if it is worth fixing it is worth generating."* The PO ruled:
*"regenerate the mapping and everything else to match the current api state."*

### `backend/scripts/regen_mapper.py` — new (`PO`)

Rewrites all 179 rows of [`api_yaml_mapper.md`](api_yaml_mapper.md) §3 from the live app and the
generated spec. **166 of the 179 changed** — every one a line number or a handler position, and not
one a route, `operationId` or schema. That distribution is the finding: the file's *contents* had
been maintained faithfully endpoint by endpoint, and its *coordinates* had rotted underneath,
because `API.md` grows above a heading and every reference below it moves. No check could see it.

**What it deliberately does not generate.** Which `API.md` section covers an operation is an
editorial judgment — `mention only — § 3.4 Password recovery` is somebody deciding which paragraph
is the right answer — so the label is preserved verbatim and only its line number re-resolved.
`**Bold**` is preserved too: `**200 free-form object**` marks a §5 defect and the unbolded form does
not. Prose, layer chains and notes are untouched. §6.1 step 4 now says regenerate rather than write
the row, and §6.2 adds `--check` to the after-every-pull routine.

### The scanner was wrong about one endpoint, and the generated table is what said so (`AUDIT`)

`GET /communities/search` has always been marked `**missing**` in §3, while `api_map_scan.py`
reported it documented. **The hand-written row was right.** The scan tested whether a path appeared
*anywhere* in `API.md` as a bare substring, and §18 documents `GET /worker/communities/search` — a
different endpoint that happens to end the same way. So a genuinely undocumented operation reported
clean for as long as the check has existed.

Fixed with a left-boundary anchor: a longer path is not a mention of a shorter one. **The
operation-side baseline moves 19 → 20**, and that is a defect surfacing rather than a regression —
the same distinction Session 58 drew about arithmetic, arriving from the opposite direction. It also
overturns one line written *in* Session 58: `/communities/search` was listed there as having
"since gained coverage", which came from trusting the scan over the row.

**Second thing that fell out of doing it mechanically:** some rows quoted the route in camelCase,
against §1's own rule that the mapper writes it as the code declares it. Normalised.

**Baselines now:** 843 tests, ruff **153** (the new script lints clean), spec up to date at 150
paths / 179 operations, **map-scan 20**, oxlint 7. The regenerator is idempotent — a second run
reports no change.

---

## 2026-08-11 — Session 58: the coherence sweep, and what a summary can still lie about

**Context.** The PO asked for a sweep across the whole surface after Session 57 — *"check if
everything fits in"* — and specifically for the spec and the story mapping. Both hold: the spec
regenerates byte-identical, and all 24 stories agree across `USER_STORIES.md`, `API.md` §16 and
`api_annotations.py`. Everything found below is a **summary that had drifted away from inputs that
were themselves correct and checked.**

### `API.md` — four stale figures over verdicts that were never wrong (`AUDIT`)

* **The document's own banner, the first factual claim in the file, read "163 operations across 138
  paths" against a spec of 179 across 150** — three sessions stale. The sentence beside it, that
  every `###` heading corresponds to a real operation, is machine-checked and was true the whole
  time. A count in prose is not checked by anything, and now says so.
* **§16.2's coverage table read 8 / 9 / 7 and now reads 15 / 6 / 3.** Its §3 row said the security
  manager had *nothing* served; five of those six stories are served, four of them since `0040`
  landed on 2026-08-10. Every per-story verdict beneath the table was right, and
  `api_map_scan.py` had been checking each of them across three files the whole time — because the
  scanner compares verdicts and does not add them up. **That is the finding worth keeping:** in a
  document with machine-checked contents, the hand-derived summary is the last line that can lie,
  and it is the first line anybody reads.
* **§16.6's headline read "90 of the 163 operations" against a spec saying 106 of 179**, and its
  table summed to 74. Four whole families were missing from it — departures, direct messages, the
  gate roster and posts, the worker's own availability — because each was added to the *spec* and
  not to this hand-made grouping. **The table was rebuilt so that every row is one
  `x-no-user-story` group in `openapi.yaml`**, same counts and same rationales, and
  `api_yaml_mapper.md` §6.3 now carries the one-line recount that produces the numbers. A group
  that splits or merges upstream now shows up as a row that no longer matches, instead of a total
  that quietly stops adding up.
* **§16.1 still opened "this branch is the admin dashboard backend", naming the resident app and
  the security gate as surfaces with no workstream.** Both have one; the gate's arrived yesterday.
  Struck through rather than deleted — it is why much of the section is worded as it is.
* **§16.7's open-work table** still listed CSV export as to-do (US-3.6 closed it for the gate; the
  admin half of US-1.6 is what remains) and still said US-2.7 waits on a service worker that was
  built on 2026-08-10.

### `api_yaml_mapper.md` — the tables were current and everything around them was not (`AUDIT`)

Sixteen operations arrived across `0043`–`0047` and every one got its row. Meanwhile the header
still said *99 operations, 686 tests, `main` @ `98d557a`*, §5 was titled "as of `98d557a`", §6.2
said 20 findings, and §5.2 claimed eleven undocumented operations when three had since gained
coverage. All corrected to the branch: **179 operations across 150 paths, 843 tests, 19 findings**
(eleven untyped bodies, eight undocumented). This file exists to catch exactly this happening
elsewhere, which is the reason to record that it happened here.

### `docs/design/README.md` (`AUDIT`)

Pointed the story matrix at **`API.md` §15**, which has been *"Not yet implemented"* since the
resident backend renumbered the sections behind it — the same stale cross-reference
`USER_STORIES.md` carried for US-3.2 and corrected a day earlier. Also still described *"two
documents today; a third would be justified by, say, the gate/security surface if it ever gets an
owner"*, and said one document was retrospective and one prospective. Five documents now, four
retrospective. The prediction is left visible: the gate did get an owner.

### `docs/design/AUTH_AND_SESSION_DESIGN.md` (`AUDIT`)

§5.2 cites `SecurityDashboard.jsx`, which Session 57 deleted. Kept, with a note — the defect it
records was real in the file that was there, and this folder's convention is that a stale citation
is a signal worth having rather than a link to tidy away. The note also records the two reads
beside it (`departmentName`, `staffRole`) that rendered a literal `undefined • undefined` to every
gate user until the same build removed them.

**Nothing in application code changed in this session.** Every baseline is where Session 57 left
it: 843 tests, ruff 153, spec up to date at 150 paths / 179 operations, map-scan 19, oxlint 7,
frontend build and three test suites green.

---

## 2026-08-11 — Session 57: the gate gets a frontend, and US-3.5 closes

**Context.** Task #93 had been open across two phases: the gate backend (`0040`, nineteen
operations, `US-3.3`–`US-3.6`) had **no consumer**, and the recommendation on record was that it
wanted its own build step. The PO ruled on 2026-08-11: *"build it."* Six steps, all shipped.

### The two demo dashboards are replaced (`PO`)

**This ruling overturns nothing written — it closes something left open.** `SecurityDashboard.jsx`
(1070 lines) and `SecurityManagerDashboard.jsx` (576) were dummy-data screens over the zustand
visitors slice; both are deleted. In their place, nine route-per-file screens under
`pages/SecurityDashboard/` and `pages/SecurityManagerDashboard/`, a `features/security/` API module
and component set, and `features/security/offline/`.

The resident-facing visitors slice **stays** — resident demo screens still consume it. Only the
security screens stopped.

**Three demo features were dropped rather than reimplemented, and each has a reason** (`DERIVED`):

* *Guard-raised approval requests.* There is no endpoint. The gap is documented at
  `resident_visitor_passes.py:134-140` — nothing in this repo lets the gate create a
  `Pending Approval` request — and inventing a client-only version would have been the same defect
  the demo already had.
* *The "Society Management Office" phone number.* Invented. No endpoint returns a community contact
  number, so any number on that screen was one somebody made up, and a made-up number on an
  emergency screen is worse than no screen. The three real national lines (112 / 101 / 108) stay.
* *The manager's editable staff array and `operatingHours`.* A second, disagreeing copy of a roster
  that already lives in the admin portal's department screens. `operatingHours` was never returned
  by anything.

### `0047_security_roster.sql` + `GET /security/roster` — a hole between two permission models (`DERIVED`)

Found in the first hour of building the shift form, which is exactly where §4.25 predicted an
unconsumed API would hide a defect. Creating a shift needs a `staffAssignmentId`; the person who
creates shifts is a security *manager* — a `security` membership ranked `manager`/`supervisor`,
since `D3` split rank from role — and **every roster read in this API sat behind the hiring
surface's `require_admin_or_manager`, which tests the membership role.** The one person the form
exists for could not fetch the guards to put in it.

One security-definer function, authorized by the predicate the shift write already trusts
(`gate_admin_community_for`). Narrower than the write on purpose: it lists only staff of
`departments.kind = 'security'`, because a shift form offering the plumbing roster offers a mistake.
No table, no view, no column — **the ERD and class diagram are untouched.** `API.md` §19 is twenty
operations; spec regenerated at 150 paths / 179 operations.

### `US-3.5` moves `partial` → `served` (`DERIVED`)

`API.md` §16.5 had graded it *"the server side is complete; the browser side is not"* since Step 7.
The browser side now exists and the section says so, replacing the old paragraph rather than
deleting it. Three properties of the implementation are recorded there because they are properties
of the *story*: every offline verdict is labelled **provisional** on screen; the device never
returns `departed` (the guest-count arithmetic needs `visitor_events`); and entries the server
rejects survive reconcile and stay visible until dismissed one at a time.

**A standing rule is deliberately overridden here.** `store/appStore.js` states that *localStorage
is deliberately never a source of domain truth*, and `public/sw.js` refuses to cache `/api/*` for
the same reason. The offline scan queue is the first durable client-owned write state in this
codebase. It is justified in `offlineGate.js`'s header: a barrier whose network dropped still has
people standing at it, and what makes an offline admission safe is not the storage but
`POST /security/offline-reconcile`, which re-verifies server-side and logs its own verdict beside
the device's claim.

### Two frontend fixes and one API touch-up (`AUDIT`)

* `Header.jsx` and `SecurityLayout.jsx` read `currentUser.departmentName` and `.staffRole`, which
  `applicationUser()` has **never** set — so every gate user has been shown the literal
  `undefined • undefined` since those screens shipped. Neither field is in the session; a guard's
  post is a property of their shift and now comes from the API. The same root cause is why the
  manager dashboard was permanently stuck on a "department unavailable" card.
* The layout's *End Shift & Logout* button ended no shift. Ending a shift is now a real
  `PATCH /security/shifts/{id}` on the Shifts screen — the one status-only change a plain guard may
  make on their own row — and the button is plain *Logout*.
* `GET /security/posts` took `include_inactive` in snake_case while every other query parameter on
  the surface is camelCase and `API.md` had promised `includeInactive` since Step 7. My own
  oversight; the alias was added rather than the documentation bent to fit it. No consumer existed
  to break.

### `docs/design/SECURITY_PORTAL_DESIGN.md` — new (`DERIVED`)

The route map, the three notification deep-link contracts `0040` has emitted since Step 7
(`/security/shifts`, `/admin/security/incidents`, `/resident/visitors` — the first two had no route
until now), and the offline design with its threat reasoning.

---

## 2026-08-11 — Session 56: the stale renders are re-rendered, the old ones archived

**Context.** The PO ordered the re-render on 2026-08-10 and asked for the old images to be
preserved: *"preserve the old ones in a folder in docs called archives with a note on what changed
and why it changed in a file in there too."* New folder `docs/archives/2026-08-10-diagram-rerender/`
holds the three replaced images plus `NOTE.md` with the per-file what-and-why.

### `docs/class-diagram/HomeBandhu-Domain-Model.svg` / `.png` — regenerated from the `.puml` (`PO`)

Rendered with PlantUML 1.2024.8 + Graphviz 15.1.1, same toolchain and style as before; the images
now show everything `0034`–`0046` added to the source. Two findings recorded in the directory
README while doing it (`AUDIT`): the previously committed PNG had been **silently truncated to
4096×4096** by PlantUML's default size limit (the full diagram is ~21500 px wide — render with
`-DPLANTUML_LIMIT_SIZE=24576`), and PlantUML 1.2025.0+ requires Java 11, so on a Java 8 machine
1.2024.8 is the jar to use. The README's "renders are one commit behind" warning is replaced by a
"renders are current" block naming versions and pitfalls.

### `docs/diagrams/erd.png` → regenerated offline; new companion `erd.svg` (`PO`, tool change `DERIVED`)

The old `erd.png` was a dbdiagram.io export roughly ten migrations behind its `.dbml` — it still
showed `vendors` and `staff_skills` (dropped in `0044`) and predated every service-operations
table. The replacement is generated **offline** by `@softwaretechnik/dbml-renderer` (SVG, plus PNG
through Graphviz `dot`), so regeneration is now a command rather than a by-hand paste-and-export —
the by-hand step is what let the image drift. The visual style changes (auto-layout, tall aspect);
the `.dbml` header documents the command and notes dbdiagram.io remains usable for a hand-arranged
export. An automated paste into dbdiagram.io was attempted first and abandoned — the editor hung on
the 81 KB document.

### `docs/diagrams/homebandhu_submission_erd.dbml` — three notes reworded, wording only (`AUDIT`)

Three `note:` strings contained bare apostrophes inside DBML single-quoted strings (`worker's`,
`resident's`, `0037's`, and a quoted `'[)'` range literal) — a parse error in any strict DBML
parser, found the moment a mechanical renderer first consumed the file. Reworded to avoid the
apostrophe; no schema content changed.

---

## 2026-08-10 — Session 55: dated departures, the employee page, and a mailbox — Phase 2's build

**Context.** Phase 2 Steps 3–9, from the PO's *service men leave and further department fine tuning
and works.md* and the four rulings taken in Q&A the same day. Two migrations (`0045`, `0046`), eight
new API operations plus one changed, four new screens, and one rule overturned by name.

### `API.md` §18.7 — the zero-commitment gate on Approve is overturned (`PO`)

`0043` refused to approve a departure while anything was booked in the leaver's name, and §18.7 said
so as the feature's centrepiece. **The PO ruled the other way on 2026-08-10**: the decision whether
and when somebody leaves is the manager's; approval picks a leave date (requested or later) and
*releases* booked work from that date onward back to the dispatch pool at a queue priority just
below urgent. §18.7 now opens with the dated model, carries the overturning note per
`design/README.md`'s rule, and the decide operation's 409 row loses "items still outstanding". The
gate survives in one named place — the direct remove, which has no decision record and no release
step — and the doc says which.

### `API.md` — three employee-management reads, a new §20, one PATCH narrowed (`DERIVED`)

`GET …/staff/{staffId}`, `GET …/staff/{staffId}/schedule`, `GET …/departures/{id}/coverage`
documented in §18.7 (the coverage zero is a statement, not an error — the PO's "if there are none,
it says so"). **§20 Direct messages**: five operations, the pair rule ("the committee" is the
`admin` role), the work-order thread's lock, names-as-snapshots and why (`profiles` is
self-read-only). `PATCH /service-providers/me` no longer accepts `displayName` — name and email are
identity, edited nowhere in settings (`PO`) — and §18.1's route text says so with the `0045` RPC
change that made it possible. §18's header count is fifty-five; `api_yaml_mapper.md` gained the
eight rows and a `messages.py` section; `api_map_scan.py --strict` is back at its 19 baseline.

### `diagrams/homebandhu_submission_erd.dbml` (`DERIVED`)

`staff_departures` gained the two dates with the ruling in the `effective_at` note; `dispatch_tasks`
reworked (nullable `work_order_id`, `departure_id`, `priority` with the 2/1/0 ladder, fifth kind,
two new partial indexes); `dm_threads`/`dm_messages` added under an 0046 banner with the
canonical-pair, one-live-thread-per-job and lock notes.

### `class-diagram/homebandhu-domain.puml` (`DERIVED`)

`StaffDeparture` gained the dates, `approve(effectiveAt)`, `conflicts()`/`coverage()`, and its note
now records the overturned refusal in italics rather than asserting it. `DirectMessageThread` /
`DirectMessage` added with the pair-and-lock note; `DispatchTaskKind` gained `DEPARTURE_REMOVAL`;
`DmThreadKind` added. **The rendered `.svg`/`.png` remain stale and labelled so** — the tooling
decision is unchanged.

### `backend/supabase/migrations/README.md` (`DERIVED`)

Rows for `0045` and `0046`, each naming its one non-obvious decision.

---

## 2026-08-10 — Session 54: Phase 2 opens — the dead-code sweep pays R16's debt

**Context.** A second plan was approved from the PO's *service men leave and further department fine
tuning and works.md* (dated departures with release-on-approve, queue priority, employee management,
worker settings, an in-app notification feed, direct messages, a chat dock on every portal). Its
Steps 1–2 are the old plan's Steps 11–12, run first so nothing new is built on unswept ground. This
session is those two steps; the feature work follows.

### `backend/supabase/migrations/0044_retire_dead_tables.sql` — new (`DERIVED`)

Drops `staff_skills` (superseded by `service_provider_skills` — D2, skills belong to the person) and
`vendors` plus `staff_assignments.vendor_id`, its only live reference (superseded by
`service_providers` — D1, a service person is a profile inside the tenancy model, not a company
outside it). Exactly the deletion R16's amendment promised by name; the amendment now carries a
"Done" line pointing here. `diagrams/homebandhu_submission_erd.dbml` loses both table blocks and the
`vendor_id` column — each replaced by a comment saying what superseded it, because a table that
silently vanishes from an ERD reads as an oversight rather than a decision.

### `backend/app/domain/roles.py` — the RBAC hierarchy deleted (`AUDIT`)

`docs/potential issues/` item 2, taken as written except for one amendment the grep forced: `Role`
itself is **not** dead — two repositories import it as the typed name for the enum values. Deleted:
`_IMPLIED_ROLES`, `effective_roles`, `role_satisfies`, `satisfies_any`, `parse_role`, and
`tests/test_roles.py` (835 → 829 tests). Kept: `Role`, `display_role`. The docstring that claimed to
be "the single source of truth" for authorization now says what the real guards are and names the
sweep that removed the pretender. Item 2's table row is marked resolved with the amendment noted.

### Frontend — one unreachable page deleted (`AUDIT`)

`pages/AdminDashboard/CreateDepartment.jsx`: its route has been a redirect to
`/admin/departments?create=1` since the Phase 1 reconciliation, and nothing imports it. The
`staffVocabulary.js` history comment now says the page is gone so its reference reads as history
rather than a pointer. Two other unreferenced files were **found and deliberately left**, because
they belong to teammates' workstreams: `features/amenities/components/AmenityTabPlaceholder.jsx`
(amenities) and `pages/Signup/SignupPage.jsx` (auth — superseded by OAuth onboarding). Recorded here
for their owners rather than deleted across the ownership line. The fallow MCP analyzer timed out
three times against `frontend/src`; the sweep used a resolver-based import scan instead, verified
by hand (it initially flagged the lazy-loaded `AmenityReportsPage.jsx`, which is live — dynamic
imports were the scanner's blind spot).

---

## 2026-08-10 — Session 53: the documentation sweep, and a renumber that was cancelled

**Context.** Step 10 of the approved build order. Four of the five items were chores; the first was a
decision, and it went the other way.

### `API.md` — the `§15`–`§19` renumber is cancelled, not deferred again (`AUDIT`)

§18 has carried a note promising a renumber in this sweep: the two new content sections sit after the
three meta-sections, and inserting them earlier *"would shift all three again and invalidate roughly
twenty cross-references."* Counting properly is what changed the answer. There are **142** `§15`–`§19`
references across this repository, and **49 of them are in this file** — a dated record whose whole
value is that it did not change afterwards.

A renumber leaves two options for those 49 and both are worse than an odd ordering: rewrite them, and
a historical entry says something it did not say; leave them, and every pointer in the log is
silently wrong. A wrong pointer is worse than an odd ordering, because a reader believes a pointer.
So the numbers stay, the note stops apologising and becomes a ruling with its reason, and this entry
records what it overturns.

### `CONFLICT_RESOLUTIONS.md` — R16 amended (`DERIVED`)

R16 parked twelve orphan baseline tables with *"build nothing against them"*, and this feature built
against them. The amendment names **which seven** are no longer parked and how: five went live
(`work_orders`, `work_order_assignments`, `worker_availability_rules`, `worker_unavailability`,
`skills`), two were superseded (`staff_skills` by D2, `vendors` by D1). The still-parked three are
listed too, because without both lists a reader cannot tell an un-parked table from an overlooked one.

It also records what R16 got **right**: the shapes held. `work_order_assignments` needed an offer
lifecycle and an exclusion constraint bolted on and nothing else. The part that did not hold was
`staff_skills`, and for a reason no schema audit could have seen — the question the product actually
asks is *which communities need my trades*, asked by somebody on no roster at all.

### `class-diagram/homebandhu-domain.puml` (`DERIVED`)

A **Service Personnel** package: `ServiceProvider`, `ServiceProviderSkill`, `SkillCategory`,
`ServiceApplication`, `BlacklistedServiceProvider`, `StaffDeparture`, `Conversation`,
`ConversationMessage`, `DispatchTask`, and the five gate classes. Nine enumerations, thirty-four
associations, and the constraint notes that carry the reasoning — why skills belong to the person,
why a departure has no `handover` status, why the shift exclusion predicate differs from the
assignment one, why the two registers are two tables.

**The rendered `.svg` and `.png` were not regenerated**, and the directory README now says so at the
top. The procedure needs `plantuml.jar` and Graphviz `dot`; neither is installed here, and an image
that silently disagrees with its source is worse than one labelled stale.

One modelling correction while writing it: `SkillCategory` was drafted as an association class
between `Skill` and `ComplaintCategory`, and this model has no `ComplaintCategory` class — a
complaint's category is a `String` attribute. It is a plain entity with a note pointing at the table.

### `product/USER_STORIES.md` (`AUDIT`)

US-3.2's *"see §14"* has pointed at the wrong section since the resident backend renumbered the
sections behind it. It means `API.md` §16.5. Corrected with the reason attached.

### `DECISIONS_NEEDED.md`

- **B2 answered by building it (`DERIVED`).** The free-text assignee was why *"complaints assigned to
  me"* was impossible; `work_order_assignments` plus `assigneeStaffId` is the answer, and
  `GET /worker/jobs` is that query. The residue is stated rather than implied: the label is kept
  beside the id, five files read it for display, and a staff member renamed after an assignment shows
  their old name on that complaint until it is next written.
- **A12 revisited (`AUDIT`).** Its reasoning rested on B2, which is now answered — and deactivation is
  still right, for a better reason. What the entry never had is the *condition*: `0043` refuses a
  removal while any job or shift is still booked in that person's name. "Does removal deactivate" was
  always yes; the question nobody asked was "and what happens to their work".
- **A22 partially answered (`AUDIT`).** *"A scheduler needs a decision about what runs it"* — there is
  one, and D8 says what: an in-process asyncio loop over `dispatch_tasks`, not `pg_cron`. That removes
  the blocker the question named without answering the question, and the entry says which.

---

## 2026-08-10 — Session 52: leaving becomes a process, and a removal that could not be safe

**Context.** Product-owner instruction: *"leaving a community requires manager permission… only when
everything has been handed over to other workers can the leave be approved… this reassignment has to
take place before the person is removed, the same applies for all servicemen regardless of
department."* `0043` is the answer; the interesting part is what building it revealed.

### The defect the instruction was really about (`AUDIT`)

**`remove_department_member` has been able to strand work since `0035`.** It set the roster row
inactive, ended the membership and returned. Nothing touched `work_order_assignments`, so a row with
`status = 'accepted'` survived a removal untouched — still pointing at tomorrow's slot, still counted
as somebody's load by `dispatch_candidates`, still rendering on the resident's complaint as *someone
is coming*. Nobody was coming, and the membership that would have carried the reminder had just
ended, so the one person who could have said so had been logged out. `security_shifts` had the same
hole: the rota read as covered by a guard who no longer worked there.

That is why the fix is not a confirmation dialog. **A departure is a state a person is in**, not an
event that happens to them, and the interval between the two is where the handover happens.

### `API.md`

- **New §18.7, seven operations (`DERIVED`).** Two on the worker's side, five on the manager's, and
  five of the seven exist only to make one refusal survivable — you cannot gate an approval on an
  empty list without giving somebody a way to empty it.
- **`POST …/members/{staffId}/remove` gains a `409` (`DERIVED`).** Refused while anything is booked
  in that person's name. Recorded as an amendment to the existing entry rather than a new one,
  because the route's contract changed rather than its purpose. It stays the one-click answer for a
  name typed into the department form by mistake.
- **`StaffMember` gains `openCommitmentCount` and `departureStatus` (`DERIVED`).** The prose says why
  the first is *not* `activeAssignmentCount`: that counts open complaints, this counts jobs and
  shifts actually booked, and a complaint can sit with nobody scheduled while a job can outlive the
  complaint that caused it. Added before the screen needed it rather than after it failed — the
  fourth time in this build a consumer would have proved a read one field short.
- **The bar's asymmetry written beside the rule it breaks (`DERIVED`).** A blacklist *releases* work
  to the engine instead of waiting for a handover. Stated in §18.7 rather than left to be discovered
  by comparing two functions, because a reader who finds it by accident reads it as a bug.

### `notifications_service.py`

- **`_FALLBACK_URLS` closes the gap §5.18 recorded (`AUDIT`).** Four `0035` hiring notifications
  rendered a title and carried no `url`, so they arrived as text nobody could tap. The comment beside
  `_FALLBACK_TITLES` said a link is *"not something a fallback can invent"* — true in general, wrong
  about these four, whose payloads already carry the id the route needs. Corrected in place with the
  original reasoning kept, per this document's own convention.

### `api_annotations.py`

- **A new `NO_STORY` verdict, `departure` (`AUDIT`).** Named by the product owner rather than by an
  interviewee, and the reason is visible in the interviews: everybody described being hired and
  nobody described quitting, because the person who quits is not in the room when the society is
  interviewed. It touches US-2.7 without serving it — the reassignment does tell a resident somebody
  else is coming, but that notification is written by `assign_work_order`, which US-2.7 already
  credits.

### `diagrams/homebandhu_submission_erd.dbml`

- **`staff_departures` added with its provenance note (`DERIVED`).** Including why there is no
  `handover` status.

### `design-of-components.md`

- **Component 3 extended (`DERIVED`).** Departure, handover and the release-versus-hand-over
  distinction, per that document's own convention.

### One stale claim corrected while passing (`AUDIT`)

`worker_communities.py`'s docstring for `GET /worker/applications` still said the list was *"the only
way a rejected applicant learns the outcome"* because `recipient_membership_id` was not nullable.
`0041` made it nullable eight hours earlier and both a rejection and an invitation are notified now.
The sentence fed the OpenAPI description, so it was wrong in a generated artifact as well as in a
docstring. Corrected with its expiry attached rather than deleted.

---

## 2026-08-10 — Session 51: the manager's side of hiring, and one vocabulary instead of four

**Context.** Step 9 of the approved build order: *"manager hiring, messages, vocabulary
reconciliation"*. Two new screens, three old ones reconciled, and — as in Sessions 49 and 50 —
building the consumer proved a read one field short.

### `API.md`

- **`rank`'s printed vocabulary was stale (`AUDIT`).** §8 has said `member | supervisor | head` since
  `0019`; `0035` replaced `head` with `manager` five migrations ago and the response example still
  showed `"rank": "head"`. Corrected, with the note that the department's *head* is still called that
  everywhere the API says `head` and is the person holding `rank = 'manager'`.
- **`serviceProviderId` documented on `StaffMember` (`DERIVED`).** New in `0042`, with the reason it
  exists rather than only its type: the two things a manager can do to a roster row take two
  different ids, and without this field one screen cannot offer both.
- **Two claims about who cannot be notified, both now false, both corrected in place rather than
  deleted (`DERIVED`).** `POST /departments/{id}/invitations` said *"the invited person is not
  notified"* and gave the schema as the reason; `GET /worker/applications` said it was *"the only way
  a rejected applicant or an invited provider learns the outcome, since neither can be notified"*.
  `0041` made `recipient_membership_id` nullable and both are notified now. The original reasoning is
  kept in the correction, because a sentence that was true when written is more useful with its
  expiry attached than removed.
- **The frontend vocabulary problem recorded beside the schema's answer (`AUDIT`).** §8's
  long-standing rule that `rank` and `role` are separate fields on purpose is exactly what three
  copies of `STAFF_ROLES` had wrong — one list answering two questions, which is why no two copies
  agreed.

### `design-of-components.md`

- **Component 3 extended (`DERIVED`).** Departments now have a hiring surface that is not a roster
  form: applications in both directions, a skill-matched candidate search, and the remove-versus-bar
  distinction. Recorded because that document's own convention requires it.

### `diagrams/homebandhu_submission_erd.dbml`

- **`staff_assignments.service_provider_id` note rewritten (`AUDIT`).** It said `0035` set it. It
  also records now that nothing *read* it until `0042`, and why that was invisible: a field only the
  write path uses looks complete in every test, because the test asserts the write.

### `supabase/migrations/README.md`

- **`0042_roster_provider_link.sql` added to the table (`DERIVED`).**

### One gap raised rather than absorbed

- **The gate has a backend and no consumer, and no step of the approved plan schedules one
  (`AUDIT`).** `0040` and `security_operations.py` closed `US-3.3`–`US-3.6` on the API in Step 7;
  Step 8 was the worker portal and Step 9 is this. `SecurityDashboard.jsx` and
  `SecurityManagerDashboard.jsx` are both demo screens over zustand and neither calls one of those
  endpoints. This is the same shape as the two defects Sessions 49 and 50 found by building
  consumers, and it wants its own step of roughly Step 8's size. Recorded in
  `plans/SERVICE_OPERATIONS_PROGRESS.md` §4.25 as a product-owner decision, not folded into the
  documentation sweep.

---

## 2026-08-10 — Session 50: a notification learns to reach somebody who belongs nowhere

**Context.** Two rulings from the product owner in one sentence — *"you can change the auth bit too,
but do document it separately in detail in a separate file in `doc/design`"* and *"fix the
notification issue too, we need to implement that too"* — and they turned out to be the same piece of
work. The notification gap `0038` left open could not be closed without changing who a notification
is addressed to, and who a notification is addressed to is an auth question.

### `design/AUTH_AND_SESSION_DESIGN.md` — new

- **Created (`PO`).** The fourth document in `docs/design`, and the first that cuts across all three
  surfaces rather than describing one. It is the review packet the PO's ruling asked for: what the
  service-operations build changed in the shared auth seam, what it fixed, and — listed as its own
  section, so restraint can be told from oversight — what it deliberately left alone. Registered in
  `design/README.md` outside the read-in-order list, because it is not a fourth surface.
- **It carries four defects nobody had reported** (§5). Each was invisible until a population arrived
  that the original decision had not imagined, which is the argument for the file rather than a diff.

### `API.md`

- **`US-2.4` moves from *Partial* to *Served* (`DERIVED`).** §16.4 had said the shortfall was one
  missing writer: `notification_service`'s renderer has carried a title for `notice.published` since
  the substrate shipped and nothing ever emitted it. `0041` closes it as an `after insert` trigger on
  `notices`. **This overturns nothing** — the paragraph in §15 that proposed a call inside
  `notices_service.create_notice` and then declined to make one asked for the notification to land
  *in* the transaction rather than beside it, and a trigger satisfies that by construction while
  leaving `insert_notice` the single-statement PostgREST write its docstring defends.
- **§5.2 and §5.3 rewritten from "any active member" to "any signed-in person" (`DERIVED`).** The
  three notification routes and the three push routes no longer require a membership. The reasoning is
  spelled out where it will be read: the caller waiting on an answer to a job application was
  precisely the caller who could not be told one.
- **The stale service-worker note in §5.3 struck through.** It still claimed nothing in
  `frontend/public/` was a service worker; that stopped being true in Session 49 and the sentence had
  only been corrected in the other place it appeared.
- **`POST /conversations/{id}/messages` gains its notification paragraph (`DERIVED`).** Including why
  the two directions are addressed differently, and the honest limit: a profile-addressed notification
  produces no SSE frame, because `sse_events.community_id` is `not null`.

### `product/USER_STORIES.md`

- **`US-2.4` → *Served*, with the reason rewritten rather than the verdict alone flipped (`DERIVED`).**
  The three places the export gate compares — this file, `API.md` §16 and
  `scripts/api_annotations.py` — moved together, which is what `api_map_scan.py --strict` checks.

### `supabase/migrations/README.md`

- **`0041_person_notifications.sql` added to the table (`DERIVED`).** Service-operations range, lowest
  free number.

### What the schema decision overturns, named as the convention requires

- **`0030`'s rule that leaving a community ends your access to what was addressed to you (`DERIVED`).**
  The read policy is now `recipient_profile_id = auth.uid()`, so it does not. The rule only read
  correctly for a caller with one membership; with several, a person removed from one society would
  lose that society's rows out of a feed that is otherwise theirs, and the badge would fall with no
  event to explain it. What ending a membership must stop is *new* notifications, and
  `notify_community_roles` already filters on `status = 'active'` at the moment of writing — which is
  where that rule belongs.

---

## 2026-08-10 — Session 49: the worker portal, and the file two stories were waiting on

**Context.** Step 8, the first step of this build to touch the frontend. Nothing here changes what
the API does; two things here change what the documentation *claimed*, because building the screens
proved one endpoint unusable and one verdict overstated.

### `product/USER_STORIES.md`

- **`US-2.7` moves from *Partial* to *Served*.** It had read *"backend-complete … `frontend/public/`
  has no service worker, so no phone can buzz"* since the resident build. `frontend/public/sw.js`
  now exists and `lib/push/pushClient.js` subscribes against `GET /push/vapid-key`. The whole gap
  was one missing file — `0030` had stored subscriptions and `app/core/push.py` had been able to
  send for weeks. `DERIVED`.
- **`US-3.5`'s stated blocker was wrong and is corrected in place.** It said the missing service
  worker was what stopped the offline gate. `localStorage` holds a bundle perfectly well without
  one; what a service worker actually buys is *surviving a reload* during the outage. The story
  stays **Partial** — its real remainder is the gate screen, which lands with the security
  frontend — but for the right reason. `AUDIT`.

### `API.md` — `GET /worker/communities/search`

- **The response shipped as `departmentNames: string[]` and could not be acted on.**
  `POST /worker/applications` takes a `departmentId`, and a provider who is not yet a member cannot
  read `GET /departments` to find one — so the search returned a list of names with nothing to
  press. Now `departments: [{ id, name }]`. Found only by building the screen that consumes it.
  `AUDIT`.
- **Two parallel arrays were rejected as the fix, and the reason is worth keeping.**
  `array_agg(distinct …)` sorts by its own argument, so an id array and a name array come back in
  uuid order and alphabetical order respectively and correspond only by accident — a bug that would
  have looked correct in every test with one department. One `jsonb_agg` of objects instead.
  `DERIVED`.

### `ARCHITECTURE.md`, `design-of-components.md`, `design/SERVICE_OPERATIONS_DESIGN.md`

- **The service worker, and what it deliberately is not.** No build-time precache manifest and no
  Workbox: Vite emits content-hashed asset names, so a hand-written manifest is wrong on the next
  build and a generated one is a versioning problem nobody asked to have. It caches successful
  same-origin GETs as they happen and reads that cache only when the network fails, and it skips
  `/api/` entirely — an API response served from cache would show a worker yesterday's jobs and call
  them today's. `DERIVED`.
- **The worker portal is guarded by a signed-in identity, not by a role.** `ProtectedRoute` reads
  `currentUser`, and `applicationUser()` returns null for anybody holding no membership — which is
  exactly the service person who has registered and not yet been hired, the population the
  registration and community-search screens exist for. `SignedInRoute` requires only
  `sessionContext.identity`; what the portal shows is decided by `GET /worker/snapshot`, whose null
  `provider` and empty `communities` are the two empty states. Same problem and same answer as
  `require_service_provider` depending on `get_current_user` alone. `DERIVED`.
- **No new zustand slices, against the plan.** The eleven existing slices are the demo half of the
  app — `createVisitorsSlice` mints its own ids — while every page that talks to the real backend
  already uses react-query, which is mounted and configured. Three hand-rolled slices would
  reimplement loading, error and refetch state and file the portal under the demo half. `AUDIT`.
- **Nine planned worker pages became six routes.** `MyCommunities`, `FindCommunities` and
  `Applications` are three views of one question and are now three tabs; `TodaySchedule` is what
  `GET /worker/snapshot` returns, which makes it the dashboard home rather than a sibling of it.
  `DERIVED`.
- **The week view is not an hour-ruled time grid.** That geometry exists to make overlaps visible,
  and `work_order_assignments_no_overlap` in `0036` refuses to write one. `DERIVED`.

---

## 2026-08-10 — Session 48: the complaint-engine handoff, and security operations

**Context.** Step 7, preceded by a handoff. Six steps of building on top of the complaint path
produced a set of questions that cannot be answered from inside the service surface, because each is
about what a *complaint* means or when it ends. They are written down for the owner of that
workstream rather than guessed quietly.

### `COMPLAINT_ENGINE_HANDOFF.md` — new

- **The framing fact, verified by reading rather than asserted: the service-operations feature never
  writes `complaints.status`.** Not once across `0036`, `0037` and `0039` — the `complaints` table
  appears only as `select * into` and as a foreign key. So there are **two state machines over one
  complaint and they are not coupled**, and a complaint can read *Pending* to its raiser while a
  technician is standing in their kitchen. Deliberate under D5 (one complaint, many work orders:
  "the complaint's status" is not a projection of any one job's), survivable because the timeline
  carries the whole story, and the single item most worth overturning knowingly. `AUDIT`.
- **Seven judgement calls handed over with the default we took and what it costs**, not as requests:
  job completion versus complaint resolution (§1); 24-hour auto-resolution (§2); the
  `complaint_events` namespace, which has no CHECK constraint and therefore no lock (§3); the failed
  visit escalation and its one dependency on the *meaning* of a complaint status (§4); priority
  inherited once and never re-inherited (§5). `DERIVED`.
- **The gap §1 names is the one nobody had noticed.** `confirm_complaint_resolution` refuses
  anything not already `resolved` (`0031`:546), and nothing moves a complaint to `resolved` when its
  work is done — so after a completed visit the resident *cannot* confirm even if they want to. The
  path from *work done* to *complaint closed* is missing its first step, and that step is a
  management act. `AUDIT`.
- **§2 corrects a misreading that was about to be inherited.** Auto-resolving off
  `dispatch_tasks.due_at` would close the complaints that got attention and leave the neglected ones
  open forever, because that timer exists only for complaints that reached triage, while
  `expected_resolution_at` exists for every complaint. The two clocks are not interchangeable.
  `AUDIT`.

### `0040_security_operations.sql` — the gate

- **Six tables and the surface that finally gives `security` something to do.** `security_posts`,
  `security_shifts`, `material_movements`, `water_tanker_logs`, `security_incidents` and
  `offline_reconcile_log`, plus nineteen operations. Hiring, skills, availability, the calendar,
  blacklisting and messaging were all reused from `0034`–`0039` verbatim — a guard is hired by
  exactly the RPC that hires a plumber — because the only thing that differs is what the work *is*.
  `DERIVED` from D11.
- **The guard is the opposite of the worker portal's, and that is the design decision.** `0039` takes
  no identity anywhere because a service person's surface is cross-community; a gate belongs to one
  society, so this resolves a community from the caller's membership. But **not** from
  `MembershipSet.default`: a guard who lives in one society and works another's barrier has a default
  membership of `resident`, and that check would refuse them their own register. `AUDIT`.
- **Two permission levels rather than one.** Recording is any gate staff; the roster is an admin, a
  manager, **or** a `security` membership ranked `manager` or `supervisor` on its roster row. The
  alternative is a system where every guard can rewrite the rota, and the alternative to *that* is
  one where the security manager cannot log a tanker. This is also the first place D3's
  rank-and-role split is honoured in code rather than described. `DERIVED`.
- **`US-3.5` was a fallback with nothing to fall back from.** The plan gives Step 7 an offline bundle
  and a reconcile and no online verification, while `USER_STORIES.md` US-3.1 says in print that
  *"nothing verifies a code at the gate"* — `0032` has minted and stored `code_hash` and `pass_hash`
  since the visitor passes shipped and **nothing has ever read either back**. `POST
  /security/gate/verify` is built first and the offline pair sits on it, so the two paths cannot
  drift into two different answers about the same visitor. `AUDIT`.
- **Plan D13's signed bundle is dropped, and the reason is that the signature protects nothing.** The
  device verifies it against a key the device holds, and the same person who can edit `localStorage`
  can delete the check beside it. What is load-bearing is that an offline admission is **provisional
  until reconciled**: the server re-runs the real verification and records its own verdict beside the
  device's claim, so a fabricated entry becomes a flagged row rather than an admitted guest.
  `DERIVED`, overturning a plan decision.
- **`US-3.1` closed, which was not in scope.** `visitor_requests.guest_count` has existed since
  `0032` and nothing had ever read it, so the obvious first-scan-in-second-scan-out verification
  would have admitted one guest of a two-hundred-guest function and turned the rest away — the exact
  failure the story describes. `verify_gate_credential` counts admissions against the column instead.
  `API.md` §16.5 had predicted the opposite in print — *"the one thing the current model cannot
  express"* — and the correction is stated inline rather than by rewriting the paragraph. `AUDIT`.
- **A CSV export is a path from the gate to a spreadsheet formula.** Every text column on these
  registers is typed by whoever is standing at the barrier, and `=`, `+`, `-` and `@` are formula
  leaders in every spreadsheet; `csv` quoting does not help, because the quotes are stripped before
  the cell is evaluated. Cells are prefixed with an apostrophe rather than stripped, since stripping
  would turn a quantity of `-5` into `5`. `AUDIT`.
- **Five story verdicts moved.** `US-3.3`, `US-3.4`, `US-3.6` and `US-3.1` to **served**; `US-3.5` to
  **partial**, because its missing half is a service worker in `frontend/public/` rather than
  anything in the backend — the same missing file that stops `US-2.7` buzzing a phone. Surface is
  now **163 operations across 138 paths**, 821 tests. `DERIVED`.

### `tests/test_openapi_spec.py` — a list that had gone stale

- **Three routers were mounted with no representative path**, under a comment reading *"Four routers
  behind one `include_router`"* while eight were. Deleting any one of their `include_router` lines
  would have removed operations and raised nothing there — and the failure would have surfaced in
  `export_openapi.py --check` as *the spec is stale*, whose obvious fix is to regenerate, which would
  have made the drop permanent and the check green. `AUDIT`.

## 2026-08-10 — Session 47: the worker's own side, and a guard that should not exist

**Context.** Step 6. `in_progress`, `completed` and `failed` have been declared in
`work_orders_status_check` since Step 4 with nothing able to write them, because the only person who
can say *I have started* is the one standing at the door and until hiring existed that person had no
account. Fourteen operations, one migration, and one amendment to `0037`. The spec moves from 130
operations to **144** across 124 paths.

### `0039_worker_actions.sql` — and the renumber it forces

- **Step 6 needed a migration the plan did not give it**, because `0034`–`0037` contain no
  worker-side write function at all. So `0039` is worker actions and **security operations becomes
  `0040`**. Nothing else moves. `AUDIT`.
- **Three `security_invoker` views** — `my_worker_job`, `my_worker_unavailability`,
  `my_worker_availability_rule` — each filtered to the caller *inside the view*, not merely by the
  policy. The policies underneath are wider on purpose (`0036` §7 lets a supervisor read their
  staff's leave), so a view leaning on the policy alone would show a supervisor their whole
  department on a screen headed "my week". `DERIVED`.
- **Five verbs on a job**, and the interesting one is `accept`: it takes `for update` on the work
  order before reading anything, so the second of two workers tapping the same offer waits, re-reads
  a job that now says `scheduled`, and is told *somebody has already taken this job* rather than
  handed a `23P01`. The exclusion constraint is still the guarantee; it is just not the thing anybody
  should have to read. `DERIVED` from D5.
- **Completing a job does not resolve the complaint.** They look like one act and are not: a resident
  whose tap still drips after the visit has a complaint that is emphatically not resolved, and
  `0031` already gives them the button that says so. A worker's word is evidence, not a verdict.
  `PO`-facing.
- **Declining writes no `complaint_events` row and notifies nobody.** The resident does not need to
  learn that five people were asked and one said no, and it keeps `job_declined` meaning the one
  thing it already meant — *the resident declined the proposed time*. `AUDIT`: reusing that word
  would have rendered a worker's decline on the resident's timeline as their own.
- **Accepting writes `job_assigned`, not a new `job_accepted`.** From the resident's side it is the
  same fact — somebody is now coming, and this is their name. `DERIVED`.

### `0037_dispatch_engine.sql` — the fourth handler, and one defect

- **`dispatch_failed_visit_escalation` exists now**, in `0037` rather than `0039`, because "what the
  engine does" living in two files is how the next reader misses half of it. Its idempotency check is
  deliberately **not** a status check: a failed job stays `failed` for good, since the answer to a
  failed visit is a *new* work order (D5), so it asks whether a newer job exists on the same
  complaint. Two hours out; the department's manager, or the community's admins where there is no
  manager on the roster. `DERIVED`.
- **`dispatch_candidates` now excludes anyone who declined *this* job.** Found while reading `0037`
  for the escalation. Without it the ordinary sequence produces the worst outcome the engine can:
  five are pinged, one declines, thirty minutes later the auto-assign picks the best candidate — and
  the decliner still ranks first and finds the job booked in their name. Scoped to the work order,
  not the person. `AUDIT`.

### `app/api/worker_deps.py` — planned, and deliberately not written

The plan put `require_worker` here and §4.4 deferred it to this step. Writing the callers showed it
should not exist. `require_membership_role` reads the role off `MembershipSet.default` — *one*
community's membership — and this is the only surface in the product that is deliberately
cross-community: a plumber hired by three societies and living in a fourth has a default membership
of `resident`, and that guard would refuse them their own job list. Widening it to *any* worker
membership still refuses a department manager who is on a roster and has been offered a job.

The question it was reaching for is *does this caller hold this assignment*, which is not about roles
and already has exactly one implementation — `is_own_staff_assignment` (`0036` §4), used by all three
views and all five verbs. So the routers are authenticated-only and **no module was added**. `AUDIT`.

### Documentation

- **`API.md`** — §18 gains *"The worker's portal"* with all fourteen operations; the engine's task
  table now shows four handlers rather than three; the operation count moves to 45, of which nine
  serve a story rather than five; the `0039`/`0040` renumber is stated where somebody looking for
  security operations will find it.
- **`ARCHITECTURE.md`** — two emitter rows, plus the note that `work_order.escalated` is the second
  emitter in this product that reports an *absence* — not the failure, which is notified
  immediately, but nobody having acted on it.
- **`homebandhu_submission_erd.dbml`** — the three "no endpoint reads this yet" notes on the
  availability tables and the task kinds are now false and say what replaced them.
- **`api_yaml_mapper.md`** — two router blocks, fourteen rows.
- **`design/SERVICE_OPERATIONS_DESIGN.md`** — §4.4 said auto-resolution after 24 hours of resident
  silence *"is implemented as specified"*, which has been false since Step 5 chose to proceed with
  the visit instead. Corrected in place with the reasoning, and it stays flagged as a default rather
  than a ruling. §4.3's fallback no longer names a module that was never written. `AUDIT`.
- **`backend/supabase/migrations/README.md`** — the number-range table gave `0025`–`0039` to the
  resident backend, which stopped at `0033`, while service operations was six files past it. Split
  into `0025`–`0033` and `0034`–`0049`. The rule it documents produced its own worked example the
  same day: `0039` went to whoever wrote first, and the plan's reservation of it lost. `AUDIT`.

---

## 2026-08-10 — Session 46: the engine, and seven functions anyone could call

**Context.** Step 5. `0036` built every transition a work order can make and not one thing that
makes a transition happen on its own; this is the part that acts unattended. It is the only step of
the twelve that adds **no API operations at all** — the spec stays at 130 operations across 112
paths, and that is the pass condition rather than a missed step.

### `0037_dispatch_engine.sql`

- **`dispatch_tasks`** — one row per future action, so the engine's whole behaviour is inspectable
  with a single `select` and a restart loses nothing. `DERIVED` from the plan's D8.
- **At-least-once, reversing the push sender's rule.** `app/core/push.py` says *"the sender may not
  duplicate"* and claims by marking a notification sent before sending it. That is right for
  something that buzzes a phone at 3am and wrong here: a dropped `resident_timeout` is a complaint
  left waiting forever with nobody coming. The claim takes a five-minute **lease**, a task may fire
  twice, and every firing function re-reads the job and returns without writing if the world has
  moved on. `PO`-visible behaviour, `DERIVED` mechanism.
- **One trigger replaces five rewritten functions.** The plan had each state-changing RPC enqueue its
  own tasks — five `create or replace`s over roughly five hundred lines, and a sixth write path
  someday that forgets. Instead an `after insert or update` trigger on `work_orders` keeps the queue
  in agreement with the status. `AUDIT`. It also deletes a mechanism: there is no separate
  "urgent complaints bypass the offer" path, only a `case` in that trigger.
- **Three handlers for four declared kinds.** `failed_visit_escalation` fires off
  `status = 'failed'`, which nothing can write until the worker portal exists. The kind goes in the
  CHECK now so the next step needs no migration; the function waits for a caller — the same posture
  `0036` took with its three unreachable statuses. `DERIVED`.
- **Two documented downgrades from the source document.** Ordering candidates *"within 1 km of an
  adjacent job"* becomes *"already has a job in this community that day"*, because no work order
  carries usable coordinates and inside one complex every job is a two-minute walk. And a resident
  who never answers has their **visit proceed**, not their complaint auto-resolved — closing a
  complaint the resident never saw is a product decision and a background job should not make it
  quietly at 2am. Both `PO`-facing; the second is worth a decision.

### `app/core/dispatcher.py`, and one wiring change

Mirrors `PushSender` — claim, act, sleep, started from the lifespan, never raising. It contains **no
dispatch logic at all** and a test asserts as much: the mapping from a task kind to an action lives
in `fire_dispatch_task` beside the actions, so a fifth kind will not touch Python. `app/main.py`
starts it beside the sender and stops it first, because it is the only one of the three workers that
writes.

### A privilege defect across four earlier migrations

Found while deciding what to grant on `0037`'s functions, by checking what `0001` and `0019` do.
**Postgres grants `EXECUTE` on a new function to `PUBLIC` by default**, so `grant ... to service_role`
on its own re-states a permission everybody already had. Seven functions had only that line:

- `notify_member` (`0030`), `notify_community_staff` (`0031`), `notify_community_roles` (`0032`) —
  any signed-in user could write a notification to any membership, or broadcast one, choosing the
  title, the body and the **url**. A notification that arrives wearing the association's name and
  leads anywhere is phishing, and the feed is the one surface a resident is meant to trust.
- `claim_push_batch`, `record_push_success`, `record_push_failure` (`0030`) — silence push
  deployment-wide, or delete another resident's subscription by endpoint.
- `expire_visitor_passes` (`0032`) — settle any community's lapsed passes.

Three of the seven granted `authenticated` **on purpose**, with a comment arguing that the callers
are feature RPCs and a resident-initiated write reaches them over the user's client. The first clause
is true and is exactly why the second does not follow: inside a `security definer` function the
current user *is* the definer. Verified from the other end too — nothing in `app/` calls any of the
seven by name. All now carry `revoke all ... from public, anon, authenticated`, and the stale
reasoning is replaced in place rather than deleted. `AUDIT`.

**Nothing in the suite can prove this fix**, and that is its honest status: no migration has ever been
applied anywhere, so these are permissions that have never existed on functions that have never run.

### Verification

`pytest` **790 passed** (was 780). `ruff` **153**, the baseline, none added.
`export_openapi.py --check` clean and **unchanged**. `api_map_scan.py --strict` **19 findings**,
unchanged. `pglast` on `0037`: 44 statements, plus a separate pass parsing the three `language sql`
function bodies, which `pglast` otherwise skips as opaque strings — that pass caught a real one: an
unqualified `order by has_adjacent_job` inside `dispatch_candidates` was ambiguous against the
function's own `RETURNS TABLE` column of the same name. Restructured so every reference is qualified.

---

## 2026-08-10 — Session 45: the job, and a constraint that has waited since the ERD was drawn

**Context.** Step 4 of the service-operations build: a triaged complaint becomes a named person at a
named hour. The step is large in surface (ten operations) and turns on one line of SQL — a GiST
exclusion constraint saying a person cannot be in two places at once, which
`docs/erd/homebandhu.dbml:614` has declared since it was written and which nothing has ever enforced.

### What this overturns

- **`CONFLICT_RESOLUTIONS.md` R16, second half.** It ruled of `work_orders` and
  `work_order_assignments` — *"tag each `Phase 2 — no v1 endpoint, no v1 RLS policy`, and build
  nothing against them."* Both are now extended, indexed, policied and served. `DERIVED` from the
  approved plan's D5. The amendment to R16 itself lands in the documentation sweep; recorded here so
  the overturn is not discovered by reading the code.

### `docs/API.md` — §18 gains ten operations, and the section stops being about registration

- **New:** `### Work orders — the state machine, before there is an engine to drive it` — a lifecycle
  table, the two constraint decisions, and eight endpoint subsections. Surface count 120 → **130
  operations across 112 paths**. `DERIVED`.
- **Changed:** §18's opening no longer says *"Six operations"* and *"Hiring is `0035` and is not built
  yet"*, both of which had been false since Step 2. `AUDIT` — found while adding the fourth
  subsection to a section whose first paragraph still described only the first.
- **New:** the one asymmetry worth stating in print — a resident may confirm and may decline, and
  **the reschedule after assignment is the supervisor's alone**, because by then it is a change to
  two people's days and only one of them is on that screen. `DERIVED`.
- **New:** a paragraph recording what Step 4 deliberately does **not** contain — no timers, no queue,
  no dispatcher — and the rule that follows from it: *every transition the engine will later make
  automatically is reachable by hand first*. `DERIVED`. This is why `POST .../assign` accepts a job
  still in `awaiting_resident`: it is the hand-operated form of the resident timeout, and without it
  the state machine would have a state with no manual exit.
- **New:** a note that `in_progress`, `completed` and `failed` are declared in the CHECK and not yet
  reachable, so their absence from the writes reads as intended rather than forgotten. `DERIVED`.
- **Changed:** §16.6 recounted from `x-user-stories` in the generated spec — **56 mapped, 74 unmapped,
  130 total**; `Feature` 42 → 47; a new group row for the five work-order operations that serve no
  story. `AUDIT`, and the count is machine-derived rather than hand-tallied for the reason §16.6
  already records about an earlier miscount.
- **New:** the observation that `0036` is the **first** of these four migrations to move the *mapped*
  count, and by five. Twenty-one operations of hiring machinery mapped to nothing; the first ten that
  put a named person at a door mapped to US-2.7 and US-2.8. `AUDIT` — that is the shape of the
  research gap stated precisely, rather than as a general complaint about the story set.

### `docs/api_yaml_mapper.md` — two more router tables

- **New:** `work_orders.py` (eight operationIds) and `resident_scheduling.py` (two), with blockquotes.
  `DERIVED`.
- **New note:** the two routers share **one service**, deliberately. Splitting it would put the two
  sides of one state machine in two files, and the transition `awaiting_resident → offered` would be
  written in one and read in the other. The routers differ because the *guards* differ; the state
  machine does not.
- **New note:** the work-order router's role guard is **coarse by construction** and cannot be
  otherwise — a supervisor holds a `worker` membership with the `supervisor` *rank*, and `0035`
  settled that rank and role are different things. `can_supervise_department` is the boundary.

### `docs/diagrams/homebandhu_submission_erd.dbml` — four baseline tables stop being dead

- **Changed:** `work_orders` gains twelve columns, three indexes and a status vocabulary; its note
  records why **one complaint may carry many** work orders and what the rejected alternative
  (assignee columns on `complaints`) would have cost. `DERIVED`.
- **Changed:** `work_order_assignments` gains seven columns and carries
  `work_order_assignments_no_overlap` in its note, spelled out in full — including why the `where`
  clause covers only `accepted` rows. `DERIVED`: constrain the *offers* and `0037` could only ever
  ask one worker at a time, which defeats the point of asking.
- **Changed:** `worker_availability_rules` and `worker_unavailability` drop `NOT NULL` on
  `staff_assignment_id` and gain `service_provider_id`, with `num_nonnulls(...) = 1`. `DERIVED`: a
  registered service person's week is not a fact about one of their four societies.
- **Note added** to both work-order tables that `btree_gist` is **not a new requirement** — `0001`
  both installs it and declares an exclusion constraint that cannot exist without it. `AUDIT`, and it
  closes a question that had been carried as open across three steps.

### A defect fixed in passing

- **`work_orders.priority`** defaulted to `normal` and was unconstrained, while `complaints.priority`
  has been checked against `low | medium | high` since `0031`. `AUDIT` — two value sets for one name
  is the same defect `0031` refused when it declined to carry two *names* for one idea. Corrected in
  place, and `create_work_order` now inherits the complaint's priority rather than inventing one.
  Free to correct because no migration in this project has ever been applied to a database; it will
  not be free a second time.
- **`app/core/pg_errors.py`** gained a `23P01` row. A double-booking caught by the exclusion
  constraint rather than by the pre-check was surfacing as a bare `400` whose message could not say
  which field was the problem. It now answers `409` alongside `23505`, because it is the same kind of
  answer — somebody else has that already. Application code, noted here because the *reason* is a
  design decision about what a client can distinguish.

### Two more, found by re-reading the migration rather than by a test

- **`work_orders_department_tenant_fkey` was `on delete set null` and could never have fired.** A
  multi-column `ON DELETE SET NULL` nulls *every* referencing column, and `work_orders.community_id`
  is `not null` in the baseline (`0001`:73) — so the action that was supposed to orphan a job
  gracefully would instead have raised `23502` and refused to delete the department, and would have
  done the same on the community cascade, where nothing orders the department delete against the
  work-order delete. Now `on delete cascade`, matching `0019` and `0035`, which the comment above it
  had already claimed. `AUDIT`.
- **`work_orders.department_id` carried two foreign keys with two different delete actions** — an
  inline `set null` from the `add column` and the composite above it. One department delete, two
  referential actions, no defined order between them. The inline clause is gone; the composite is the
  only FK on the column. `AUDIT`. `0035` keeps both of its FKs only because both of its actions agree.
- **`conversations` gained the composite tenant FK the other three tables already had.** `0038`
  denormalises `community_id` onto the thread *specifically* so the read policy can call
  `is_community_admin(community_id)` without joining the department — which means a row whose two
  columns disagreed would be readable by the wrong community's admins. `open_conversation` sets it
  correctly; nothing defended it afterwards. `AUDIT`, and the ERD block records the addition.

Every one of these is free today only because no migration in this project has ever been applied
anywhere (`potential issues` #4). None of them would have been.

---

## 2026-08-09 — Session 44: the conversation, and a guard that belongs in the database

**Context.** Step 3 of the service-operations build: the chat a department has with a service person,
before and after hiring. The step is small; the interesting part is where its authorization lives.

### `docs/API.md` — §18 gains four operations and one asymmetry worth explaining

- **New:** `### Conversations — the guard that is not in the router`, covering
  `GET`/`POST /conversations`, `GET /conversations/{id}` and `POST /conversations/{id}/messages`.
  Surface count 116 → **120 operations across 104 paths**. `DERIVED` from the approved plan's Step 3.
- **New:** a table stating the three different answers a non-participant gets — absent from the list,
  `404` on the read, `403` on the write. `DERIVED`: a `403` on the read would confirm a thread exists,
  which would make a department's conversations with every other provider enumerable by walking ids.
  The write can afford `403` because the caller has already named a thread they can see.
- **Changed:** "What is not here yet" no longer lists `0038`; the seventeen-operation count in that
  paragraph becomes twenty-one.

### `docs/api_yaml_mapper.md` — a fifth service-operations router table

- **New:** `conversations.py` with four operationIds and four blockquotes. `DERIVED`. The first
  records that this is **the only router on the API with no role guard at all**, and why that is the
  design: a conversation belongs to one department *and* one provider, so participation is a property
  of the row and no role a router could check would answer it.

### `docs/diagrams/homebandhu_submission_erd.dbml` — `0038`'s two tables

- **New:** `conversations` and `conversation_messages`, with the unique constraint named in the index
  note because it is load-bearing rather than incidental — it is what lets `open_conversation` be an
  upsert instead of a read-then-write. `DERIVED`.
- **New note:** why `conversation_messages` has **two** author columns rather than one. `AUDIT`: an
  invited provider holds no membership in the community, so a single `author_membership_id` could not
  address the party the whole surface exists to reach.

### `docs/plans/SERVICE_OPERATIONS_PROGRESS.md` — §6.4 amended before it was built

- **Changed:** the recorded plan for Step 3 gained a fourth route and lost a trigger, both **before**
  the code was written, per §1's working agreement. `AUDIT`: with the three routes originally written
  down, nothing created a thread — an id is required to post, so the first message could never be
  sent. The trigger was dropped because §6 declares read policies only, so there is no second writer
  for a trigger to defend against.
- **Changed:** participation narrowed from "managers and supervisors" to `can_manage_department`.
  `DERIVED`: this is the *hiring* conversation; a supervisor's conversation is with a complainant
  about a job, which is `complaint_comments`.

---

## 2026-08-09 — Session 43: hiring, and three constraints that were rejecting valid writes

**Context.** Step 2 of the service-operations build: a service person applies or is invited, a
department manager decides, and accepting turns one row into three. The product owner also confirmed
PostGIS is enabled and asked for every defect found so far to be fixed rather than parked.

### `docs/API.md` — §18 gains eleven operations, and §7 loses a lie

- **New:** `### Hiring — one negotiation, two directions`, covering `GET`/`POST` `/worker/communities`,
  `/worker/communities/search`, the three `/worker/applications` routes, and the six
  `/departments/{id}/…` hiring routes. Surface count 105 → **116 operations across 101 paths**.
  `DERIVED` from the approved plan's Step 2.
- **Changed:** `POST /complaints/{id}/comments` — the error table traded
  `409 conflict — unknown visibility` for `422 unknown_visibility`, and a note now states that
  `resident` is a *wire* word which the service translates to the stored `public`. `AUDIT`: the
  request was previously forwarded unmapped, so **every comment posted through this endpoint failed**
  against `complaint_comments_visibility_check` — including the frontend's, which hardcodes
  `resident`. The wire vocabulary documented here is unchanged and remains the contract.

### `docs/diagrams/homebandhu_submission_erd.dbml` — the service tables, and four corrections

- **New:** `service_providers`, `service_provider_skills`, `blacklisted_service_providers`,
  `service_applications`, plus a prose block naming what `0035` changed on the existing tables.
  `DERIVED`.
- **Fixed:** the `departments` and `staff_assignments` blocks were still **baseline-only**, missing
  every column `0019` added — contact details, opening hours, SLA, kind, status, rank, shift,
  community_id, display_name, and both partial unique indexes. `AUDIT`, found while preparing to add
  this feature's own rows to them. Adding to a block that was already wrong would have baked the
  error in.
- **Changed:** `departments.kind` note `internal | vendor | hybrid` → `service | security`;
  `staff_assignments.rank` `head | member` → `manager | supervisor | member`;
  `staff_assignments.shift` gains `Day` and `Rotating`, loses `Morning`. `DERIVED` from `0035`.

### Three vocabulary contradictions closed, all of them live failures

Recorded together because they are one defect wearing three hats: **a CHECK constraint and a Python
validator that allow different sets of words.** None was a tidy-up; each was rejecting writes the
product makes.

| Column | Database said | Code said | Now |
|---|---|---|---|
| `complaint_comments.visibility` | `public`, `internal` | `resident` (default) | translated in `vocabularies.py` |
| `departments.kind` | `internal`, `vendor`, `hybrid` | `service`, `security` | `service`, `security` |
| `staff_assignments.shift` | `Morning`, `Evening`, `Night`, `Full Day` | `Day`, `Evening`, `Night` | `Day`, `Evening`, `Night`, `Full Day`, `Rotating` |

`AUDIT`. The `kind` sets did not intersect at all, so every department write naming a kind was a
`422`; only writes omitting it worked, which is why nobody noticed. All three were free to correct
because **no migration in this project has ever been applied to a database**. They will not be free a
second time.

### `staff_assignments.rank` — `head` becomes `manager`, and `head` stays the wire word

`PO` ruling D3, implemented. Four vocabularies disagreed: SQL said `head|member`, `API.md` §8 said
`member|supervisor|head`, the ERD said `manager|supervisor|worker`, and three frontend screens
carried three more lists. **`supervisor` was documented in `department_schemas.py` and rejected by the
CHECK constraint** — an advertised rank no write could produce.

`AUDIT` found the part the plan missed: relaxing the CHECK alone breaks the schema, because `0019`
has four other references to the word. `apply_department_head` is the *only* function that ever sets
a rank and it wrote `'head'`; `department_overview` projects `head_name` by matching on it. Both are
replaced in `0035`. **The API keeps saying `head`** — that is what the department screens and `API.md`
§8 call the person who runs a department, and renaming it would break a working screen for nothing.

### `docs/plans/SERVICE_OPERATIONS_PROGRESS.md` — the journal

§4.6 and §4.7 (facts that changed the plan), §5.8 and §5.9 and §5.10 (what landed), §7.1 closed —
PostGIS is confirmed enabled, so the D7 fallback is not taken. `btree_gist` remains unconfirmed and
is flagged, because Steps 4 and 7 declare exclusion constraints that need it.

---

## 2026-08-09 — Session 42: planning documents get a folder, and the service surface gets a design

**Context.** The service-operations build is mid-Step 1 of 12. The product owner asked for two things
before it continues: that every unit of work be **written down before it is done**, so a stop at any
point is resumable weeks later by someone who was not here; and that the planning documents, which
had accumulated loose in `docs/` alongside the reference documents, be gathered into one folder.

### `docs/plans/` — **new folder**

Nine documents moved in. Seven were tracked and moved with `git mv`, preserving history:
`ADMIN_DASHBOARD_BUILD_PLAN.md`, `ADMIN_DASHBOARD_PLAN.md`, `AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md`,
`BACKEND_PLAN.md`, `IMPLEMENTATION_PLAN.md`, `RECONCILIATION_ADDENDUM.md`,
`SCHEMA_RECONCILIATION_PLAN.md`. Two were untracked working-tree files:
`SERVICE_OPERATIONS_PLAN.md` and `SERVICE_OPERATIONS_PROGRESS.md`, which had been sitting in
`docs/design/` where they did not belong. — `PO`

**The distinction the folder now makes explicit,** stated in its `README.md`: `design/` is
retrospective and answers *why the built thing is built that way* — if it and the code disagree, the
document is a bug. `plans/` is prospective and answers *what we were going to do* — if it and the
code disagree, **neither is wrong**, because a plan is a record of intent. A half-implemented or
abandoned plan stays here at full length, because the reasoning in it is what the next person needs.
Nothing in `plans/` may be cited as evidence of what runs. — `DERIVED`

**Every live cross-reference was repointed in the same change.** Links inside the moved files that
pointed up into `docs/` (`../API.md` ×7, `../CHANGE_LOG.md`, `../CONFLICT_RESOLUTIONS.md`,
`../FRONTEND_MEETING_AGENDA.md`, `../FRONTEND_WIRING_AUDIT.md`, `../ARCHITECTURE.md`, and thirteen
`../../frontend/src/...` paths), and links from outside that pointed at them —
`docs/ADMIN_REGISTRATION_FLOW.md`, `docs/ARCHITECTURE.md`, `docs/erd/homebandhu.dbml`,
`docs/potential issues/README.md`, `backend/app/api/v1/admin_api.py:11` and
`backend/supabase/migrations/0018_settings_on_baseline.sql:20`. — `DERIVED`

**This file's own historical entries were deliberately left alone.** Roughly forty of them name
`BACKEND_PLAN.md`, `IMPLEMENTATION_PLAN.md` and the rest at their old paths. Those entries are a
dated record of what was true when they were written; rewriting them to say `plans/` would falsify
the log to make a `grep` tidier. The move is recorded here as a new entry instead — which is what
this log is for. — `AUDIT`

**One caveat worth flagging rather than burying.** `AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md` is the
auth workstream's document, not ours. It was moved because the instruction said *all* planning
documents, and its inbound reference in `ARCHITECTURE.md:5` was repointed — but it is the one file in
the set whose owner should get a veto.

### `docs/plans/SERVICE_OPERATIONS_PROGRESS.md` — rewritten as a live work journal

Was a status snapshot; is now a resumable journal with a **§0 "Resume here"** naming the next action
precisely enough to start work without re-deriving it from the plan. — `PO`

The working agreement in §1 is literal: **before each unit of work the intent is written into §6;
after it, the entry moves to §5 with what actually happened.** A unit of work is one migration, one
router-plus-service-plus-repository triple, one test module, one documentation sweep — not one line.

**Why a journal rather than a checklist.** A checklist records *that* something was done. It does not
record the fact discovered halfway through that made the plan wrong, and that is the expensive one to
reconstruct — §4 exists for exactly those, and already holds three. — `DERIVED`

Also corrected: the branch was recorded as `documentation/api-updates`; it is `services-and-security`.
— `AUDIT`

### `docs/plans/SERVICE_OPERATIONS_PLAN.md` — marked frozen

An approved plan is now explicitly not editable to match what happened. Deviations are recorded in
the progress document *with the fact that forced them*, so the difference between "we decided
otherwise" and "reality disagreed" stays visible. Three such deviations already exist — the
`skill_categories` join table that could not work in a per-community schema, `blacklisted_service_providers`
moving forward one migration, and `MembershipSet` losing its raising method to avoid `app/domain`
importing `app/core`. — `DERIVED`

### `docs/design/SERVICE_OPERATIONS_DESIGN.md` — **new file**

The third design document `design/README.md` anticipated: *"a third would be justified by, say, the
gate/security surface if it ever gets an owner."* — `PO`

**It deliberately does not restate the decision record.** `D1`–`D15` were made with the product owner
across three rounds of questions and live in the plan; relocating them here would present them as
derived when they were ruled. The design document confines itself to what the plan does not cover:
how the new surface stays coherent with the two that already exist — a nine-row paradigm checklist,
the three findings a reader of `design/` would not otherwise meet, four costs stated under a heading
that admits they are costs, and the one place the surface deliberately diverges (`D3`'s `rank`
vocabulary). — `DERIVED`

**The most load-bearing paragraph is §2.1.** RLS was *already* multi-community —
`is_community_member(uuid)` (`0019:81`) has always been an `exists` over every active membership. The
single-community assumption lived in exactly one query. That is why a service person belonging to
several communities at once is a change to one function rather than to the tenancy model, and why
every guarantee in `ADMIN_DASHBOARD_DESIGN.md` §2 about per-request revocation survives untouched.

### `docs/design/README.md`

The document table gains the service row, and a new paragraph says **where the decisions live** —
`design/` answers why the built thing is built that way, `plans/` holds what we intended, including
the full `D1`–`D15` record. Without it a reader of the new design document would reasonably conclude
the decisions had gone missing. — `DERIVED`

### `docs/API.md` — new §18, service personnel

Six operations backed by `0034`, and the section leads with what makes them different: **they are
the first on this API whose caller holds no community membership.** A plumber exists before any
society has heard of them. — `DERIVED`

**§18 sits after the three meta-sections rather than before them, and says so in print.** Inserting
it as §15 would shift §15/§16/§17 for the third time and invalidate roughly twenty cross-references
across four documents *mid-build*. The renumber is deferred to this feature's documentation sweep,
where §19 for security operations lands too and one pass covers both. Recording the reason inline
was the point — an unexplained out-of-order section reads as an accident and gets "fixed" by
someone who had no way of knowing. — `AUDIT`

**Two things already in print are overturned, each named explicitly** per the `design/README.md`
rule. `product/USER_IDENTIFICATION.md:55-65` and §16.1: *"a staff member is a name on a roster, not
an account"* — false as of this section; a service person registers, holds an account, and receives
a real `worker` or `security` membership when hired. And `CONFLICT_RESOLUTIONS.md` **R16**'s *"build
nothing against them"* — `skills` is the first of the twelve parked tables to be un-parked.
`staff_skills` is superseded and is deleted at the end of the feature, because skills belong to the
**person** and not to a roster row: the "which communities need my skills" search has to run for
someone nobody has hired yet. — `PO`

**Coverage is unchanged, deliberately.** All six operations trace to no user story. Every story this
feature eventually closes — US-2.7, US-2.8, US-3.3 through US-3.6 — is about work being *done*,
which begins at hiring, which is `0035` and not built. Tagging any of them would inflate §16.
Surface counts in the header updated to **105 operations across 91 paths**. — `DERIVED`

### `docs/api_yaml_mapper.md`

A router table for `service_providers.py` with all six rows, plus a §7 rescan row. Operation-side
findings stay at **20** — the same as before this work — because all six are documented in both
places. — `DERIVED`

Two notes recorded under the table for the next person who scans. It is the only router in §3 that
declares no membership dependency, which is deliberate rather than an omission to tidy away. And
`GET /skills` is the only collection on this API that returns a bare array instead of a `Page`:
§1.6's one-shape rule is about collections that grow, and this one is twelve rows of seeded
reference data. — `AUDIT`

### `docs/plans/SERVICE_OPERATIONS_PROGRESS.md` — §4.4 and §4.5

Two facts found while building, recorded because neither is recoverable from the code afterwards.

**§4.4 — `worker_deps.py` was deferred from Step 1 to Step 6.** Checked against Step 1's actual six
operations, neither guard the plan put there has a caller: all three write RPCs resolve the provider
from `auth.uid()` and raise `P0002` when there is no row, which `pg_errors.translate` already turns
into a 404. A dependency reading the same row a moment earlier would add a round trip per request and
a second home for the "are you registered" rule. The *reasoning* the plan attached to it is kept
verbatim, because it is the part that matters: `get_service_provider` must depend on
`get_current_user` alone, never on membership, or a registered-but-unhired provider is 403'd out of
the screens that let them apply — a system in which nobody can ever be hired. — `DERIVED`

**§4.5 — the additive seam was not additive, and the suite caught it.** Declaring
`Depends(get_membership_set)` on `get_active_membership` reads identically to FastAPI and breaks
every *direct* call. There are direct calls: `tests/api/test_session_flow.py:603` invokes it
positionally to prove the role comes from `community_memberships` rather than from a token claim.
Fixed by keeping the `Principal` parameter and deriving inside the body. **A changed parameter type
is not additive; it only looks additive from inside dependency injection** — which is exactly the
class of breakage D14 promised would not happen, and the reason `tests/test_membership_set.py` now
pins the direct-call form explicitly. — `AUDIT`

---

## 2026-08-09 — Session 41: the pull that widened an error contract without touching a route

**Context.** Local `main` was four commits behind `origin/main`, so Session 40's sweep had been run
against a stale base and had to be re-proved. It survives: spec current, scan unchanged at 20
findings with zero story findings, 694 tests passing (8 more than before — the pull brought its own).
But the rescan-after-every-pull rule earned its keep once.

### `backend/scripts/api_annotations.py` → `docs/openapi.yaml`

- `POST /onboarding/community` now explains its route-specific **422** rationale alongside
  401/403/409/500/503, and its description no longer claims 409 is "almost always a name collision"
  or that 503 means only "not provisioned". **422 was already present in the generated OpenAPI
  operation** through the application-wide `include_router(..., responses={422: ...})` declaration.
  **AUDIT.** Commit `7d830e1` rewrote `onboarding_service.create_community` to catch
  `APIError` specifically and route it through `app.core.pg_errors.translate`, which maps
  `23503`/`23514`/`23502`/`22P02`/`22004` to `ValidationError`. It
  also added the `founder_onboarding_unavailable` 503 for any failure it cannot attribute to the
  caller, and left 409 `onboarding_failed` reachable only from the row-shape guard.
  **Nothing mechanical could catch the missing rationale.** No path, method, or response model moved,
  and the route diff was empty. 404 was deliberately *not*
  added: `translate` can emit it, but this operation looks nothing up by id, and the convention set
  by `POST /complaints` is to declare the reachable subset rather than the whole mapping.

---

## 2026-08-08 — Session 40: the matrix was current, its index was four days behind

**Context.** A sweep of the user stories in `docs/product/` against the API surface, asking whether
every relevant endpoint and every story is accounted for. The answer on the code side was yes and
had been checked before: all 99 operations carry a story tag or a written reason for having none
(51 / 48), the type breakdown reconciles exactly, all 24 stories have a section in `API.md` §16, and
its 8 served / 9 partial / 7 none is self-consistent. The drift was entirely in the documents that
restate that answer.

### `docs/product/USER_STORIES.md`

- **Six `Backend:` verdicts corrected.** `AUDIT` US-2.2, US-2.5, US-2.6, US-2.8 and US-2.12 read
  *partial* or *none* after they closed; US-2.3 read *none* after it moved to partial. The file's own
  header calls this line an index of `API.md` §16 and says not to maintain the two independently —
  and the two were maintained independently, because `§16` and `api_annotations.py` are edited by the
  work that changes a verdict and this file is not. **Every error was in the same direction: the
  backend under-reported what it had built.** That is the direction nobody notices, because nobody
  audits a claim that work is unfinished.
- **Four stale *reasons* rewritten under unchanged verdicts.** `AUDIT` US-2.1 said "there is no push
  transport" (built), US-2.4 said "nothing carries it to a resident" (the transport carries it; the
  emitter is missing), US-2.9 said the directory was unreadable by residents (`GET
  /directory/contacts` serves it), US-3.1 said "nothing issues one" (`POST /visitor-passes` does). A
  correct verdict resting on a false reason is worse than a wrong verdict, because it survives review.
- **Three links to `API.md#14-user-stories--endpoints` repointed at §16.** `AUDIT` The section moved
  twice, in `README.md`, `USER_IDENTIFICATION.md` and `USER_STORIES.md`. Every reader following the
  traceability trail from the requirements landed nowhere.

### `docs/API.md`

- **Eight tagged operations added to their story's own section.** `AUDIT` The spec said they serve the
  story and §16 never named them: `POST /amenity-bookings/{id}/damage` and `/charges` (US-1.2),
  `POST /invoices` (US-1.6), `GET /notifications` (US-2.1, US-2.4, US-2.7), `PATCH /complaints/{id}`
  (US-2.7 — which had no endpoint table at all, only prose) and `POST /admins` (US-2.9). §16 is the
  human-readable evidence for a verdict; a verdict whose evidence is incomplete is an assertion.
- **§16.5 gains an endpoint table for US-3.1.** `AUDIT` See below.

### `backend/scripts/api_annotations.py` → `docs/openapi.yaml`

- **`US-3.1` added to `STORIES`, and tagged on `POST /visitor-passes` and `/cancel`.** `AUDIT` This was
  the one genuine traceability defect the sweep found. §16.5 has credited those two operations with
  issuing and revoking a scheduled, time-boxed access code since `0032`, and argued the case in
  prose — but the story had no entry in the annotation table, so the generated spec recorded **no
  operation at all** as serving a story the matrix calls *partial*. The verdict does not move: the
  requirement US-3.1 is actually about is *scan*, and nothing verifies a code at the gate. Neither do
  the counts — both operations already carried US-2.2, so it stays 51 served / 48 none.
- **The root cause, stated once.** `AUDIT` The export guard is directional. It refuses to build unless
  every **operation** declares which stories it serves, which is why the operation side has never
  drifted. Nothing checked that every **story** a verdict credits has an operation declaring it, or
  that the three places recording a verdict agree. Both gaps produced exactly one class of error each,
  and both were invisible to `--check`, to the test suite, and to `api_map_scan.py` as it stood.

### `backend/scripts/api_map_scan.py`

- **A fifth question: do the three records of each story's verdict agree?** `DERIVED` Reports
  `STORY VERDICT` when `USER_STORIES.md`, `API.md` §16 and `api_annotations.py` disagree, and
  `STORY UNBACKED` when a story credited as served or partial has no operation declaring it. Run
  against the pre-fix state it produces seven findings — the six stale lines and US-3.1 — so it
  catches precisely what a human sweep took an afternoon to find. Verified by injection: flipping one
  verdict in memory fires the check.
- **Why in the scan rather than in the exporter.** `DERIVED` The exporter must stay able to build; a
  prose document being behind is not a reason to fail a code build. The scan is the pull-time artifact
  and already carries the other four questions, so this is one more line in the same output.

### `docs/api_yaml_mapper.md`

- **§6.1 step 5 and §6.2's fifth question.** `PO` The standing rule now says explicitly that a commit
  changing a story's verdict changes it in all three places. Recorded because the rule as written
  ("all four artifacts move together") was followed and still permitted this drift — `USER_STORIES.md`
  was not one of the four.

**Verified after the change.** `export_openapi.py --check` up to date · `686 passed` ·
`ruff check scripts/` clean · `api_map_scan.py` reports 20 findings, unchanged, all in §5, with all
24 stories agreeing across all three records.

---

## 2026-08-08 — Session 39: the spec was not stale, and now we can prove it every time

**Context.** The testing team reported that part of `openapi.yaml` looked out of sync with `main`. It
was not. On `main` @ `98d557a` the spec regenerates byte-identical (`export_openapi.py --check`
passes), all **99** live API operations are documented, the spec documents nothing that does not
exist, and the suite is green at 686 tests. But the complaint pointed at something real, and the
audit that disproved the stated cause found it.

### `docs/api_yaml_mapper.md` — new

- **A per-source-file index from backend code to the spec and to `API.md`.** `AUDIT` A generated spec
  can be perfectly in sync and still wrong: `--check` proves the yaml matches what FastAPI
  *declares*, never that the declaration matches what the handler *does*. Nothing in the repository
  watched that gap, so nothing caught the eleven operations whose success body the spec describes as
  `{}` or `additionalProperties: true`. The mapper makes the gap visible per file, and its §5 records
  each one with a verdict — because an undocumented endpoint nobody wrote down is indistinguishable
  next month from one deliberately left free-form.
- **`operationId` is the anchor, not the path.** `DERIVED` It is unique across the spec, greppable
  from all three files, and derivable from the handler name in both directions. Paths repeat across
  methods and change spelling between `{amenity_id}` and `{amenityId}`; the id does neither.
- **The standing rule is written into the file itself (§6).** `PO` Code, spec, `API.md` and the
  mapper move in one commit; every pull from the repository is followed by the scan in §6.2. Others'
  endpoints arrive without our documentation, and the pull is the only moment anyone reliably looks.
- **The rule ships with a tool, `backend/scripts/api_map_scan.py`.** `DERIVED` A rule that depends on
  somebody remembering to diff two tables by eye is a rule that lasts one sprint. The script asks the
  four questions §6.2 asks, prints one line per finding with file and line, and `--strict` exits
  non-zero for CI. It reports 20 findings today — precisely the eleven untyped bodies and nine
  undocumented operations of §5, so the scan's output and the mapper's verdict list agree exactly.
  Anything it reports that §5 does not carry is new by definition.

### `API.md` — one direction of its coverage claim was never checked

- **Nine operations have no reference section.** `AUDIT` The header promises every `###` heading
  corresponds to a real operation, which is true and is enforced. The reverse was never checked, and
  it hides the whole access-requests family (7), both `communities` reads, and `PUT`/`DELETE
  /dashboard/amenities/{id}` — present in the spec, present in §16.6's traceability table, absent
  from the reference. Recorded in the mapper §5.2 rather than fixed here: three of those files belong
  to the other workstream and this was an audit, not an issue fix.

### Findings recorded, not fixed

- **`GET /auth/methods` is the one outright defect.** `AUDIT` It documents its 200 body as `{}` and
  never mentions the **304** it answers to a matching `If-None-Match`; `AuthMethodsResponse` and
  `AuthMethod` are absent from `components.schemas` entirely. Proved against a live `TestClient`, not
  inferred. It is the first endpoint a tester meets, because the sign-in screen calls it before
  rendering — the likeliest thing behind the original report.
- **The amenity CRUD trio cannot be documented yet.** `AUDIT` `dashboard_repository` returns a
  different row shape when `schema_generation() == "legacy"`, so the response shape is
  deployment-dependent and there is no single true schema to write down until that branch resolves.
- **Three things that look like defects and are not**, recorded so they are not "fixed" later: the
  two SSE routes declare `text/event-stream` deliberately; the 14 apparent error-status over-claims
  are reachable through `pg_errors.py`'s SQLSTATE mapping, which no static walker crosses; and
  `edec5df`'s "missing amenityId" was a **frontend** bug calling paths that never existed, against a
  spec that was correct.

---

## 2026-08-08 — Session 38: issue #22, an email nobody had to prove

**Context.** GitHub issue #22, assigned to this workstream: the confirmation link's **Confirm email**
button arrives disabled, and an account that never confirmed can sign in anyway. Two defects that
read as one bug, with two different owners — one is a Supabase dashboard setting, the other is a hole
in this repository. Recorded here because the spec changed and because the second defect turns on a
rule this log already carries.

### `openapi.yaml` — sign-in now refuses an unconfirmed address

- **`POST /auth/password/sign-in` gains a `401 email_not_confirmed`.** `AUDIT` The backend took
  whatever GoTrue returned. With Supabase's **Confirm email** setting on, GoTrue refuses the grant
  itself and the hole is invisible; with it off — the reported state — GoTrue returns a perfectly
  valid session for an address nobody has proven they own, and nothing downstream looked. Both cases
  now end at the same error code, so the answer stops depending on a dashboard toggle that no file in
  this repository can see. The check reads GoTrue's own user record at the provider exchange, **not
  the JWT claim**: `docs/BACKEND_CHANGES.md` rules that an OAuth JWT need not carry
  `email_confirmed_at`, and `test_registration_contracts.py` pins that join and invitation flows must
  not gate on it. Google identities are untouched — the provider already verified the address.
- **The error names its reason instead of hiding behind "invalid email or password".** `DERIVED` The
  anti-enumeration rule that governs the rest of this flow does not apply here: the branch is only
  reachable by someone who supplied the correct password, so they already know the account exists.
  Staying vague would buy nothing and strand a real user with no idea what to do.

### `openapi.yaml` — `POST /auth/email/resend` stops being a placebo

- **The route now actually sends.** `AUDIT` It returned *"a confirmation email will be sent"* and sent
  nothing; the previous description said so plainly, on the reasoning that Supabase exposed no resend
  primitive safe to call through this BFF. It does — `auth.resend({"type": "signup", ...})`, the same
  shape as the recovery call already in use. That was worth revisiting the moment sign-in started
  refusing unconfirmed accounts: a user whose confirmation link is dead now has nowhere else to go.
  Provider errors stay swallowed, so **200 is still not a delivery receipt**, and the neutral response
  is unchanged.

### The disabled button — configuration, plus a frontend that hid it

- **The root cause is a Supabase email template, not code.** `AUDIT` `EmailConfirmationPage.jsx` reads
  `token_hash` from the query string and disables the button when it is absent. It is absent because
  the **Confirm signup** template is still GoTrue's default `{{ .ConfirmationURL }}`, which routes
  through `/auth/v1/verify` and lands on the page with nothing to spend.
  `docs/SUPABASE_AUTH_SETUP.md` step 3 already specifies the correct template
  (`?token_hash={{ .TokenHash }}&type=signup`); the project does not match its own document, so the
  document needs no change. Raised as item 5 of `potential issues/`.
- **The page no longer fails silently.** `DERIVED` A greyed-out button with no explanation is the
  worst possible presentation of this: nothing to read, nothing to click, no way to tell a
  misconfigured template from an already-used link. With no hash to spend the page now says so and
  offers a resend, which is also the first caller of the endpoint fixed above. `AuthEntryPage` does
  the same for a sign-in refused with `email_not_confirmed`. Under the standing rule this would have
  been flagged and left; the **product owner's ruling that issue-fixing may cross into anyone's code**
  is what makes it part of the fix.

### `API.md` — the authentication chapter was describing a design that no longer exists

- **§3 rewritten from phone/SMS OTP to what is actually served.** `AUDIT` The section carried a
  warning admitting it documented OTP "which is what the code does today" — untrue for some time: no
  OTP endpoint exists, and the one route it documented (`POST /auth/refresh`) took a `refresh_token`
  body it has not accepted since the cookie session landed. Replaced with the real sixteen operations
  in five groups: discovery and CSRF, OAuth, email/password, recovery, session lifecycle.
- **§1.2 rewritten.** `AUDIT` It described bearer-only auth against `SUPABASE_JWT_SECRET`, a
  `user_role` claim from an access-token hook, and an `ADMIN ⊇ RESIDENT` hierarchy enforced by the
  guards. All three are gone: authentication is cookie-first, no role claim is read, and
  `require_membership_role` matches exactly. The dead hierarchy in `app/domain/roles.py` is now
  called out in the section rather than left to mislead — raised as item 2 of `potential issues/`.
- **§4 corrected.** `AUDIT` It documented an invite keyed on `phone` and `apartment_id` with a
  `role`; the endpoint takes `intended_unit_id` and `invitee_email`. The two endpoints that actually
  redeem an invite were missing entirely.
- **§1.8 and the settings note corrected.** `AUDIT` Rate limiting named `/auth/otp/request` and
  `/auth/redeem`, neither of which exists; it now names the four real unauthenticated surfaces. The
  claim that "there is no visitor backend" predates migration `0032` — `requireVisitorPreapproval`
  still has no reader, but for a different and narrower reason, which is now the one given.
- **Header block refreshed.** `AUDIT` It advertised 59 operations across two workstreams; the surface
  is 99 across 86 paths.

### `issue fixes/` — a new folder

- **`issue fixes/22.md`, the full account of this fix.** `DERIVED` One file per closed issue, named
  by its number. It carries what a commit message cannot: the two bugs and why they were unrelated,
  the dashboard toggle the whole flow's security was resting on, the `email_verified` gate we nearly
  wrote and the two artifacts that exist to prevent it, and the dependency between the two fixes —
  repairing the bypass without repairing the resend endpoint would have converted a security hole
  into a lockout. Written for a reader who was not here.
- **`issue fixes/README.md`, the convention for the folder.** `DERIVED` A folder with one file in it
  teaches nobody anything, and the next person writing a fix document would have had to reverse it
  out of `22.md`. The README states it directly: how to read one (a table mapping "what you want to
  know" to the section that answers it), the section-by-section skeleton to copy, and seven rules —
  of which two carry the real weight. **Name the bug that existed, not the bug that was reported**,
  because #22 was filed as one bug and was two. And **write down the fix you rejected**, because a
  wrong fix that looked obviously right to the author will look obviously right to the next reader,
  who will then improve the code back into the bug. Also fixes the boundary against the sibling
  folder: findings that are not this issue go to `potential issues/` and are linked, never smuggled
  into the fix write-up.

### `potential issues/` — a new folder

- **Eight findings written as ready-to-raise GitHub issues.** `AUDIT` Everything turned up while
  fixing #22 that is not #22, ordered by cost of leaving it, each naming file and line and a command
  the reader can run to confirm it. Kept out of `DECISIONS_NEEDED.md` because these are not decisions
  waiting on the product owner — they are defects and debts waiting on someone's time.

---

## 2026-08-08 — Session 37: what Swagger saw in the spec

**Context.** The spec was loaded into Swagger Editor and came back with a warning nobody in this
repository had run a tool against: *`requestBody` does not have well-defined semantics for GET, HEAD
and DELETE operations*, on `DELETE /push/subscriptions`. Auditing the whole document for that class of
finding turned up a second, quieter one. Both are recorded here because both were introduced by
decisions this log already carries — the first overturns one of them.

### `openapi.yaml` — removal moved off `DELETE`

- **`DELETE /push/subscriptions` → `POST /push/subscriptions/unregister`.** `AUDIT` **This overturns
  the note written with the endpoint on 2026-08-04**, which chose a `DELETE` with a body, argued
  correctly that the endpoint URL is a device identifier and must not go in a query string, and then
  concluded that a `DELETE` body was safe because `frontend/src/lib/api/client.js` forwards it to
  `fetch`. The reasoning about the query string still holds and is why this is not the obvious fix; the
  reasoning about the body does not. RFC 9110 leaves content on a `DELETE` undefined — clients may
  decline to send it, intermediaries may strip it — so "our current client happens to send it" was
  never the right test to have applied. That note named the remedy itself: *"the fix is a second path,
  not a query parameter."* It is now taken. Nothing was calling the route — no frontend file
  references `/push/subscriptions` — so the change costs nothing today and would have cost a silent
  production failure later.
- **`_check_request_bodies` added to `scripts/export_openapi.py`.** `DERIVED` A build error, not a
  review note: a body that arrives in development and is stripped by a proxy in production is the
  worst failure available, and the class is trivially detectable. The same bargain as
  `_check_coverage` — the check is what keeps the decision from quietly reverting.

### `openapi.yaml` — the fourteen unlabelled tag groups

- **Six of the twenty tags in use had a description; fourteen did not.** `AUDIT` Not a validity error,
  which is why nothing had caught it: the document is schema-valid either way, and the groups still
  render. But a reader opening Swagger UI met `resident-money` next to `money`, and `resident-home`
  next to `dashboard`, with no line of text saying which is which — the exact question the spec is
  read to answer. All twenty are now described, in a deliberate order that runs outward from the
  caller's session to the admin surface to the resident surface, and `_apply_tags` fails the build
  when a tag is undescribed or a description outlives its tag.

### What the audit cleared

- **Schema validation passes** against OpenAPI 3.1 (`openapi-spec-validator`), and a checker written
  for this pass found no dangling `$ref`, no duplicate `operationId`, no undeclared or unused path
  parameter, no operation missing a summary, description or response, and no colliding path shape.
- **The four OAuth routes that declare `307` and no `2xx` are correct** and were deliberately left:
  a redirect is the success case there.
- **Story coverage is unchanged and complete** — 99 operations, every one carrying either
  `x-user-stories` or a classified `x-no-user-story`.

---

## 2026-08-04 — Session 36 (part 5): three sections that had stopped being true

**Context.** Found while answering *"are there any steps left?"*. All three are documents describing a
state of the world that a later change had moved, and none of them was wrong when it was written —
which is the failure mode a change log exists to catch, because nothing fails when prose rots.

### `API.md` §15 — *Not yet implemented*

- **Its opening said "none of these exist yet, and calling them returns `404`" and then listed
  nothing.** `AUDIT` The sentence survived from when §15 was a forward plan; both build orders have
  since completed, so the section's whole subject changed from *what is coming* to *what still will
  not answer, and why*. Rewritten to say that, and to sort what remains into the three kinds it
  actually contains: unapplied wiring, halves of features owned outside this repository, and stories
  whose missing part was never an endpoint.
- **It cited migrations `0010`–`0017` as the unapplied set.** `AUDIT` Those files have not existed
  since they were quarantined and rebuilt onto the baseline as `0018`–`0023`; the resident range then
  added `0028`–`0033`. Corrected to the true statement, which is stronger and simpler: *no migration
  has been applied to any database, `0001` included*. The four places where the database rather than
  the API makes a guarantee true are now named — `0001`'s GIST exclusion constraint on
  `amenity_bookings`, `0031`'s SLA rule, `0032`'s code hashing, `0033`'s settlement RPCs — because
  "the migrations are unapplied" understates what is unproven.
- **Two gaps documented in §16 had no entry in §15.** `AUDIT` `POST /notices` emitting no
  notification, and the absent `frontend/public/sw.js`. Both were correctly recorded as the reason a
  story is partial; neither appeared in the section a reader consults to find out what does not work
  yet. A gap recorded only in the traceability matrix is a gap recorded for whoever is auditing
  coverage, not for whoever is about to wire a screen.

### `DECISIONS_NEEDED.md` F1

- **The same `0010`–`0017` numbering, in the item that tells the Supabase holder what to apply.**
  `AUDIT` Worse here than in §15, because F1 is an instruction rather than a description, and it named
  eight files that cannot be found. Now says *every migration, `0001` included*, and keeps the old
  numbering visible in a parenthetical so anyone holding a printed copy can tell it is the same item.

### `design/RESIDENT_BACKEND_DESIGN.md` §4 — the capability inventory

- **"**Support** is the *current* backend state" — it is not, and had not been since step 1.** `AUDIT`
  Roughly twenty rows read *No*, *Blocked* or *table yes, no endpoint*; §9 was written to close them
  and did. The fix is deliberately **not** to update the rows. §4 is the input the build order was
  derived from, and a design record that silently rewrites its own premises to match the outcome stops
  being evidence of anything. The preamble now dates the survey (2026-08-03, before any of this was
  built) and points forward to §9 and `API.md` §12–§14 for present tense.

---

## 2026-08-04 — Session 36 (part 4): a traceability audit of the generated spec

**Context.** A pass over `docs/openapi.yaml` asking, of every one of the 99 operations, whether it is
actually there and actually annotated the way this project says it annotates things — rather than
trusting that it is because the export ran without complaint.

**What was already sound.** Every route the application registers appears in the spec, and no path in
the spec is absent from the code. Every operation carries a summary, a description, error responses
beyond the framework's automatic `422`, a `500`, and either `x-user-stories` or `x-no-user-story`.
That is not luck: `export_openapi.py` refuses to build when the annotation table and the live routes
disagree, which is why adding an endpoint fails the export until its errors and its stories are
declared. The guard has been doing its job.

**What was not.** Two things, both found by asking questions the guard cannot ask.

### Eight parameters had no description

`booking_id`, `pass_id`, `notification_id` and the `Last-Event-ID` header reached the spec undescribed
— 90 of 98 parameters documented, and the eight missing were all on endpoints added after the
annotation layer was built. Added to `PARAMETER_DESCRIPTIONS`, and each says the thing a reader
cannot infer from the name: that `booking_id` is scoped by `is_own_booking` rather than by community,
that approve and reject need the pass to be undecided or the answer is `409`, and that a malformed
`Last-Event-ID` is read as `0` rather than refused, because the browser sets that header itself and
rejecting the reconnect would leave a client no way to recover. `AUDIT`.

### `POST /invoices/{id}/payments` was claiming a user story it had not earned

It carried `US-2.12` — *"Reliable booking payment confirmation"* — since the money layer was built.
[`USER_STORIES.md`](product/USER_STORIES.md) scopes that story to **amenity-booking** payment; this
operation records a maintenance payment an administrator took by hand. Three things in this
repository already said so and were not reconciled with the table: §16.4's endpoint list for
`US-2.12` never included it, `RESIDENT_BACKEND_DESIGN.md` §11.7 says the story is about the booking
transaction, and the resident invoice path beside it carries an explicit written refusal of the
identical mapping. The role text claimed for it — payment and record moving together — is true and is
a property of **every settlement in this backend**, which is what made it plausible enough to survive
review. Now `x-no-user-story` with a `Feature` classification that states what it is and what it was.

The recount that follows from it: **51 operations serve a story, 48 serve none**, `Feature` 21 → 22.
API.md §16.6 updated, including its own header, which still said *"47 of the 98"* after the surface
grew to 99. **A traceability matrix that flatters is worse than one that admits a gap**, because the
gap is the finding — §16.6 exists to argue that 48 untraced operations are a fact about the story set
rather than a defect in the API, and an overclaim inside it undermines the argument it is making.
`AUDIT`.

---

## 2026-08-04 — Session 36 (part 3): the home aggregate, and four defects in step 6

**Context.** Steps 7 and 8 of `RESIDENT_BACKEND_DESIGN.md` §9, plus a review pass over step 6 before
building on top of it. `GET /resident/snapshot` is the last endpoint of the build order. **The
resident backend is complete; no migration has been applied to any database.**

### Four defects in step 6, and what each of them was

**The read path and the write path disagreed about whose invoice it is.** `0033` §2's own comment
names this as the worst possible bug in the file — *"a resident able to pay a bill they cannot
see"* — and then the repository shipped it: `GET /invoices/mine` filtered on `membership_id`, which
is a **narrower** rule than the `is_own_invoice` the settlement RPC enforces. `0021` drops the NOT
NULL on `invoices.membership_id` precisely so a bill can be raised against a **flat**; such a bill is
payable through the second branch of the predicate and matches no membership filter. The list now
calls the same function the write path does, and two tests assert the predicate rather than the rows,
because nothing else in the suite would have noticed. `AUDIT`.

**The Paid tab was defined as "not payable", so it contained cancelled bills.** `is_payable` is false
for four different reasons — paid, void, draft, nothing outstanding — and only one of them means
paid. A voided ₹12,000 bill appeared in the resident's list of settled ones. The tabs now filter on
the wire `status`, which is the word the screen shows and the question a tab actually asks. **Same
defect class as step 5's `is_current`**: a computed flag reused for a split it does not describe.
`AUDIT`.

**Drafts were reaching residents.** A draft invoice is one an admin has not issued — no number, no
promise, nothing to pay — and it was arriving as an amount owed on a bill nobody had sent. The
resident projection now excludes them at the view. `AUDIT`.

**A replayed idempotency key called the gateway first and then reported the wrong verdict.** Two
faults in one path. The service ran the simulator *before* the RPC that detects the duplicate: with a
pure function that is merely untidy, and with a real provider behind the same seam — which is the
entire claim the module makes — it is a double charge on every double-tap, the one failure an
idempotency key exists to prevent. And the response was built from the fresh simulation rather than
the stored row, so retrying with a card that declines would have answered `failed` beside a
`settledStatus` of `Paid`. Both RPCs now **return the payment rather than an id**, a `find_*` lookup
runs before the gateway, and a key that already settled a *different* invoice is a `409` instead of a
friendly success against a bill that remains unpaid. `AUDIT`.

Two smaller ones fell out of the same read: `amenity_financial_events` gained an `instrument_label`
so a replayed booking payment can be described from the row that recorded it, and `0033`'s claim that
the unique index would refuse a duplicate was corrected — the index is on
`(community_id, event_type, payment_reference)`, so a decline followed by a fall-through would have
written a `payment` beside the `payment_failed` and confirmed a booking off a card that declined.

### The activity strip is the notification feed — §5.7 corrected rather than obeyed

§5.7 reserved `member_activity` for the home screen's activity list, reasoning that a second activity
table would mean two feeds that disagree. **The reasoning is right and its premise is not.** Nothing
in this project writes `member_activity` — not a trigger, not a service, and not the admin dashboard,
which reads `audit_events` instead — so serving the strip from it would have shipped a list that is
empty by construction and stays empty. §5.8 had already made `notifications` the durable record of
*every user-visible event*, which is exactly what an activity strip shows; writing those events a
second time would have created the very pair of disagreeing feeds §5.7 set out to prevent. `AUDIT`,
overturning `RESIDENT_BACKEND_DESIGN.md` §5.7 as written.

### The aggregate owns nothing

`GET /resident/snapshot` is a projection of the endpoints around it: every part of it is the model
the endpoint that owns it returns, and the only things computed here are counts. That is a constraint
rather than an economy — a home screen that renders a bill in its own shape will one day show a
different amount than the Payments page, and the resident will believe the smaller one. It is also
the only endpoint in this backend that needed **no schema change at all**. `DERIVED` from §5.1.

Three rules in it came from reading `DashboardHome.jsx` rather than from the design: the visitor
counts are **guests, not passes** (one pass for a party of twelve is twelve people at the gate); the
bill offered is the maintenance one, or else the **oldest** payable rather than the newest, so an
overdue bill is never hidden behind a fresh one; and the badge counts the whole feed rather than the
five events returned, because a badge drawn from a page is wrong the moment anybody scrolls.

`dues.isPartialTotal` is the one field invented here. The outstanding total is summed over the bills
actually read, and a resident holding more than one read carries would otherwise be shown a number
that is quietly too small — which is worse than a number with a caveat, because they pay what they
are shown and believe they are square. `DERIVED`.

### US-2.3 moves from none to partial, and stops there

The story asks for one-tap access *"including a home-screen widget"*, and its own note reads
*"Backend: **None** — a client concern, but it needs endpoints that do not exist."* Those endpoints
exist now, which is what moves the row off zero. A home-screen widget is an operating-system surface
and this is a web application with no native client (`PO`, 2026-08-03), so no endpoint closes that
half. Coverage is **8 served / 9 partial / 7 none** across 99 operations. `DERIVED`.

---

## 2026-08-04 — Session 36 (part 2): the resident's money and home

**Context.** Step 6 of `RESIDENT_BACKEND_DESIGN.md` §9. `0033_resident_money_and_home.sql`, eight
operations, and the first thing in this backend that says anything about money on a resident's
behalf. **US-2.12 closes.**

### The gateway is a simulator, and every row it writes says so

`payments.provider` has existed since the baseline and the admin's `record_payment` writes
`'offline'`. Resident payments write **`'simulator'`**, and that string is the most important thing
in the migration. A demo database becomes a staging database becomes, occasionally, the thing
somebody reconciles against a bank statement — and if simulated money is recorded as `offline`, then
on the day a real gateway arrives **nobody can ever separate the money that moved from the money that
did not.** That is not a recoverable mistake; the information was never recorded. `DERIVED` from
§11.1.

It is also the honest answer to the rule §5.5 has carried since the first draft — *never report a
payment as succeeded when no money moved*. The row says `succeeded`, because inside the simulated
gateway it did; and it says `simulator`, because that is which gateway said so. Both facts recorded,
neither implied.

### The simulator is a pure function, and that is the entire architecture

`simulate(instrument) -> SimulatedOutcome`. No database, no network, no clock beyond one expiry
comparison, no randomness. The RPC it feeds **takes an outcome and never decides one**, so swapping
in a real provider changes one Python module and leaves the router, the RPC and the migration
untouched.

Deterministic on purpose: a demo that fails one time in ten is a demo nobody can run twice. And the
failure paths are the reason the simulator exists rather than a stub that always succeeds — with a
real provider in test mode a decline is a card you have to go and find, and here it is one expiry
date. `DERIVED` from §11.6.

**Only the published test card numbers are accepted**, which is the part worth arguing. A simulator
that took any Luhn-valid number is one that *will* be handed a real card — by a tester being
thorough, by someone in a demo audience being helpful. At that moment this is an application holding
a live PAN with none of the obligations discharged that holding one implies. Stripe's sandbox can
accept anything because Stripe is PCI-DSS certified infrastructure; copying the affordance without
the substrate is the mistake. `AUDIT`.

Nothing about the card survives the call: number, CVV and expiry are `SecretStr`, read once, and
discarded. What is stored is `•••• 4242`.

### A declined payment is a `200`

The request was well-formed, authorized, processed and produced a durable record; the *payment*
failed. A `402` would put an ordinary business outcome in the same client branch as *"your session
expired"* and leave a payment id to be dug out of an error envelope with nowhere to put one. Clients
branch on `status`. `DERIVED` from §11.5.

### US-2.12 closes on the transaction, not on the gateway

Its recorded reason for being partial was *"no payment gateway is integrated"*, and that was reading
the story as being about payments. It is about *"a successful payment always yields a confirmed
booking"*, and the pain point — money deducted, no booking — is a payment recorded in one transaction
and a confirmation in another with a crash between them.

`settle_amenity_booking_payment` does both or neither. On a decline it writes the attempt with its
reason and **leaves the booking exactly as it was** — the half that gets forgotten, and the half the
story is about. `PO`'s story text, read closely; this overturns the earlier `partial` verdict.

### Five things the build added that §7 did not anticipate

**`unit_contacts`, a table.** §7 assumed `household_overview` could serve *add a number to my flat*
from rows that already exist. It cannot. The prototype implements it by inventing a whole user, and
here `profiles.id` references `auth.users` — a person with no account cannot be a profile, and
manufacturing a membership for a phone number would put somebody in the member count who cannot log
in and never agreed to join. A flat contact is a different kind of thing and gets its own table.
`AUDIT`, against the frontend gate.

**`resident_notice_overview`.** Notices looked like a read of an existing table. Two vocabularies and
one exclusion is a projection.

**RLS on `notices`, `unit_residencies` and `departments`.** None of the three had any, so every
authenticated user in the project could read every notice, every department, and — worst — **who
lives in which flat**. Fifth instance of the timing rule: the policy ships in the migration that
first serves the data. `AUDIT`.

**A resident may now read their own booking charges.** `0023` made the ledger admin-only, reasoning
that what residents were charged is not a community-wide fact. True of the community and false of
the resident: the one person entitled to know what a booking costs is the one being asked to pay it.
The policy gains an own-booking clause and nothing more.

**`payment_failed`, a fifth `amenity_financial_events` type.** The four that existed had no word for
*this did not go through*.

**And one inherited gap closed while passing:** `0021` gave `invoices_read` two routes to an invoice
— by membership, and by current residency of the billed unit — and gave `invoice_line_items_read`
only the first. A resident who inherited a vacant flat's bill could see the total and not one line of
what it was for. Both now go through `is_own_invoice`, which is why that function exists rather than
a repeated predicate.

### Two things stated rather than solved

**The failure demonstration is not reachable from the current UI.** `Payments.jsx` renders UPI as the
only enabled method and its Confirm button collects no instrument at all, so a UPI payment with no
handle has to succeed or the endpoint could not be called from the screen it was built for. Showing a
decline needs a VPA field or the card fields the modal currently disables. Recorded in `API.md` §14.3
rather than worked around.

**`idempotencyKey` is required and the rule for minting it cannot be enforced from this side.** One
key per press of Pay; a *new* key once a decline has been shown. The key identifies an attempt, not
an invoice — backwards, it produces either a double charge or an unpayable bill. §14.4.

### One scope call

`GET /amenity-bookings/mine` is in §6 under *Amenities* and step 6's title does not mention it. It is
built here anyway, because `POST /amenity-bookings/{id}/pay` needs a booking id and nothing else in
this API would have given a resident one. Shipping a pay endpoint whose id has no source is the same
defect class this session spent its first half fixing.

### Artifacts

`API.md` (**new §14**; meta-sections renumbered 14→15, 15→16, 16→17 with every cross-reference
updated; §16.2 coverage now 8/8/8; §16.4 US-2.4, US-2.9 and US-2.12 rewritten; §16.6 recounted at
51 + 47 = 98), `openapi.yaml` (regenerated), `migrations/README.md` (20 views, 65 functions, 46
called from Python), `RESIDENT_BACKEND_DESIGN.md` §7 and §9, the ERD, the class diagram, this file.
Tests: 612, up from 548.

---

## 2026-08-04 — Session 36 (part 1): six defects in the visitor surface

**Context.** A review of step 5 before starting step 6. Six findings, none of which any test was
failing on. Four are in `0032`, one was inherited from `0022`, and one is a mismatch with the only
client that exists.

### A guest standing in the living room was filed under History

`is_current` was *"open and not past its window"*, which excludes `checked_in` — so the moment a
visitor walked through the gate their pass left the front tab. The prototype's own predicate is
`['Checked Out', 'Rejected'].includes(status) || date < today` (`Visitors.jsx`), which keeps them
there, and correctly: a guest who is inside is the one pass a resident might actually need. The clock
now constrains only the states where nobody has arrived. `AUDIT`, against the frontend gate.

Worth naming as a class rather than an instance: this was an expiry rule applied to a state that
expiry does not describe. The column's comment claimed it existed so the split could not drift from
the frontend's — while drifting from it.

### `Expired` was a status nothing ever wrote

The uniqueness argument recorded in part 2 above — *"expired passes returning their numbers to
circulation is what makes six digits sufficient"* — **was not true when it was written, and this
entry overturns it.** An index predicate must be IMMUTABLE, so it cannot ask the clock; `live` in
that index means a *status*, and no code path in this project has ever set `expired`. A pass that
lapsed at six o'clock would have held its number for the life of the project.

`expire_visitor_passes(community)` makes the claim true: it settles that community's lapsed passes
immediately before a new code is minted into its live set. Not a trigger — a trigger cannot fire on
the passage of time — and not a cron job, which would be a second deployment artifact for a property
one statement holds. Passes therefore lapse lazily, which is what `is_lapsed` on the view is for.
`DERIVED` from the uniqueness deviation, which depended on it.

The same review found the neighbouring case: `valid_until` was `expected_at + ttl`, and the form
floors the date at today but not the *time*. A four-o'clock pre-approval for a nine-o'clock arrival
minted a pass whose window had already closed — unusable, reported as nothing, and retired by the
very next sweep. The TTL now runs from the arrival **or from issue, whichever is later**.

### Six statements that had matched zero rows since `0022`

`feature_catalog` holds ten codes, seeded once in `0001`, all hyphenated: `visitor-management`,
`security-gate-management`, `complaint-management`. `0022` wrote `('complaints',
'complaint_management')`, `('visitors', 'visitor_management', 'security')` and four more in the same
shape, and `0032` copied the habit. **None of them matches anything.**

Nothing failed, because an `update ... where` that selects nothing is a success. Every module would
have sat at the column defaults — `sort_order = 0`, `backend_status = 'absent'` — and the Settings
screen, which exists precisely so a toggle cannot imply a backend that is not there, would have
reported that none of this backend exists. **The one screen built to be honest about what is missing
would have been the one lying.** `AUDIT`.

`0022` is corrected in place; it has never been applied, and a fix-up migration would have left the
wrong statement in the file for the next reader to copy, which is exactly how `0032` acquired it. All
ten modules are listed now — the section header has always claimed to seed the ten that
`onboardingModules.js` offers, and four were never mentioned.

### The gate could read a pass and not the log of what was done to it

`visitor_requests` got a three-audience policy; `visitor_events` got two. A `security` member could
see a pass and not its event history — which is the only record a check-in leaves. The `security`
clause had been spelled out inline in one policy and forgotten in the other, in a file that quotes
`0019`'s warning that *"a predicate copied and pasted is correct twenty times and will eventually be
wrong once"*. `is_community_security(community)` now joins `is_community_member` and
`is_community_admin`, and both policies call it. `AUDIT`.

### `visitorName` was required, and no client can produce one

The resident's pre-approval form collects a purpose, a date, a time and a guest count. **There is no
name field on it.** `visitor_requests.visitor_name` is `not null`, so `createVisitorsSlice.js`
composes a label — *"Guest group"*, *"Family event group"*. The API demanded the field anyway.

It is now optional, and the same label is composed in the service when it is absent. The rule lives
in one place, and it is the product's rule rather than a client's rendering choice: it ends up in the
notification a gate reads and in an event log that outlives the screen. Still accepted when present,
because the gate's own screen does collect a name. `AUDIT`, against the frontend gate.

### A collision the database could not resolve and the resident could not act on

Two residents in one community can be handed the same six digits; the partial unique index refuses
the second. The refusal is right and it is not the caller's problem — nothing about their request was
wrong. The database cannot retry either, because it holds a hash and no way back to a code, so
re-minting can only happen where the plaintext is, which by design is the service and nowhere else.
Five attempts, then a `409`: an unbounded retry against a full code space is an outage rather than a
retry. `DERIVED` from the uniqueness deviation.

### One consequence recorded rather than built

*Show QR* on the Visitors screen rebuilds the payload from the store, which works only because the
prototype keeps the plaintext forever. Against this API the code arrives once and no read returns it,
so a client that wants that button must keep what the `201` handed it. Losing it loses the QR, not
the pass. `API.md` §13 now says so, and names the shape a recovery endpoint would take — mint a
*fresh* code, invalidate the old one — without building it, because reissuing a pass already works.

### Artifacts

`API.md` §13 (`visitorName`, `isCurrent`, the `409`, the TTL floor, two new subsections),
`openapi.yaml` (regenerated, 77 paths / 90 operations), `migrations/README.md`,
`RESIDENT_BACKEND_DESIGN.md` §9 step 5, this file. Tests: 548, up from 539.

---

## 2026-08-04 — Session 35 (part 2): visitor passes

**Context.** Step 5 of `RESIDENT_BACKEND_DESIGN.md` §9. `0032_visitor_passes.sql`, six operations,
and the first credential this backend mints. **US-2.2 closes; US-2.1 does not.**

### The code is a credential, so it is never stored and never re-read

§5.4 asked for a hash and a plaintext returned once. It is built one step stronger: both the security
code and the QR token are generated **in the API and never sent to the database at all** — only their
hashes are RPC parameters. There is no statement log, slow-query log or replication stream in which a
code could appear. `visitor_pass_overview` does not select the hash columns either, so a list read, a
detail read and all three decisions are structurally incapable of carrying one. `DERIVED` from §5.4.

The entropy is stated rather than quietly fixed. Six digits is about twenty bits, because a resident
reads it down a phone line; what carries the difference is that a code is unique only among *live*
passes in one community, that passes expire, and that **any future gate-verification endpoint must
rate-limit by community**. That endpoint does not exist. The obligation is recorded in `API.md` §13
and §14 so whoever builds it inherits it rather than rediscovering it.

### Uniqueness: a deliberate deviation from §9

§9's sketch says `code_hash text unique`. Global uniqueness would have broken in production: 900,000
values against a project-wide index collides at a few hundred live passes, and every collision would
be one community's pass failing to issue because an unrelated community held that number. Replaced by
a **partial unique index on `(community_id, code_hash)` over live passes only** — a code has to be
unambiguous where and when it is used, and expired passes returning their numbers to circulation is
what makes six digits sufficient rather than merely tolerable. `DERIVED`, and it overrides §9.

### The setting that had never been read

`community_settings.visitor_code_ttl_minutes` has been writable from the admin settings screen since
`0018`, under the comment *"Reserved by the ERD for a subsystem that does not exist. Nothing reads
it."* These endpoints are the reader. **A control that stores a value nothing consults is worse than
a missing control, because it looks like it worked.** `AUDIT`.

`require_visitor_preapproval` still has no reader and correctly so — it governs whether the *gate*
may admit someone with no pass, which is the half that does not exist.

### Row security, fourth instance of the same timing rule

`visitor_requests` and `visitor_events` have had none since the baseline, so any authenticated user
could read every visitor row in the project — names, phone numbers, and which flat is expecting whom.
Tolerable only while nothing served them; this migration is what stops that being true, so the policy
lands in the same file. Same rule as `0028`, `0030` and `0031`. The new element is a **third
audience**: `security` has to see a pass it neither raised nor owns.

### One fan-out function, not two

`notify_community_staff` (`0031`) reaches admins and managers — the right audience for a complaint
and the wrong one for a gate. Rather than write a second loop, `0032` introduces
`notify_community_roles` and replaces `0031`'s function with a one-line delegation. Two copies of a
fan-out loop is how one of them ends up filtering on `status = 'active'` and the other does not, and
the one that forgets is the one that notifies people who have left the community. `DERIVED`.

### The catalogue row that was three features

`0022` had `visitors`, `visitor_management` and `security` sharing one `absent` row. `0032` splits
them: `visitors` → `partial`, **`security` stays `absent`**. Rounding it up because a neighbouring
feature moved is how a status board stops being worth reading. `AUDIT`.

### API.md

- **New §13 Visitors.** The three meta-sections shift: *Not yet implemented* 13 → 14, *User stories*
  14 → 15, *Changelog* 15 → 16, with every in-prose cross-reference updated. The 2026-07-31 entry
  recording the earlier 14 → 15 move is left untouched — it is history, not a reference.
- §15.2 coverage: resident 3/6/3 → **4/5/3**, totals 6/10/8 → **7/9/8**.
- §15.4: US-2.1 and US-2.2 were compiled as one row and are now two verdicts. A matrix that keeps
  stories paired after the thing joining them is gone reports the weaker of the two as the state of
  both.
- §15.5: US-3.1's *issue* and *revoke* now exist; **scan** does not, and that is what the story is
  about, so the verdict is unchanged. US-3.2's blocker moved from a missing endpoint to a product
  ruling nobody has made.
- §15.6 recounted from the spec: **47 mapped + 43 unmapped = 90**. All six new operations map, so the
  unmapped table is unchanged.
- §15.7 item 6 closed for the resident half.

### Other artifacts

- **ARCHITECTURE.md** — `notify_community_roles` and the visitor emitter row.
- **ERD** — the six `0032` columns, the partial-index reasoning, and `visitor_pass_overview` with a
  note on why its column list stops short of both hashes.
- **Class diagram** — router, service and repository; the schema package renamed `0029-0032`.
- **Migrations README** — the `0032` row, the numbering rule applied without incident, and recounted
  totals: **15 views, 58 functions, 43 called from Python**.

---

## 2026-08-04 — Session 35: reading the complaint surface back

**Context.** Before step 5, a pass back over step 4. Five findings, four of them in code written last
session and one older. None came from a failing test — every one came from reading two artifacts next
to each other and finding they disagreed.

### The status filter answered correctly and returned the wrong list

`GET /complaints?status=Resolved` translated through `status_to_storage`, which answers *what do I
store when the user picks this* — the right question when writing and the wrong one when filtering.
Two stored statuses render as `Resolved` (`resolved`, `closed`) and two as `In Progress`
(`acknowledged`, `in_progress`), so the filter returned a strict subset of the rows the same list
displays under the word the caller typed. **A resident filtering by `Resolved` would not have seen the
complaints they had themselves confirmed** — which reads as lost data, not as a filter.

Fixed with `complaint_status_filter`, derived by *inverting* `_COMPLAINT_STATUS_TO_WIRE` rather than
restating it. A hand-written second map is a promise that two dictionaries get edited together, and
this module exists because that promise is not kept. Words the surface never renders — `Closed` — are
a `422` rather than an empty match: a caller asking for one is guessing at a vocabulary this API does
not speak. `AUDIT`.

> This is the more dangerous sibling of the Session 34 `hasMore` finding. A filter that is spelled
> correctly and answers wrongly produces no error, no empty page and no complaint from the user —
> nothing about it looks like a mistake.

### The timeline bound kept the wrong end

The timeline and comment thread were read oldest-first under a 200-row bound. The order and the bound
are not independent choices: together they keep the *opening* of a long-running complaint and discard
everything that has happened since. On the one screen where the bound could ever bite, that is exactly
inverted — the resident opens a months-old complaint and sees it frozen on the day they raised it.

Both now read newest-first and are reversed in the service. `hasOlderEvents` and `hasOlderComments`
are measured with a one-row probe past the bound. Same rule as the amenity envelope, arrived at from
the other direction. `AUDIT`.

### `complaint_overview.is_unread` was per-raiser, not per-caller

The view's own comment said per-caller and the join said `raised_by_membership_id`. They are the same
row on the only surface reading the view today, and stop being the same row the moment anything else
does — `mark_complaint_read` deliberately writes one row per membership so an admin cannot clear a
resident's marker, and the view would have ignored every row it wrote for anybody but the raiser. Now
a lateral `max()` over the caller's own rows; `max()` rather than a plain join so a user with two
memberships cannot turn one complaint into two list rows. `AUDIT`.

### A ten-entry label map that nothing called

`_EVENT_LABELS` was defined with four lines of comment explaining a fallback that no code path
reached, and `ComplaintEvent` shipped a raw `event_type` for the client to translate. Wired up as
`label`, kept **alongside** `type` rather than replacing it: a UI keying behaviour off a translated
string is a UI that breaks when the wording changes. `AUDIT`.

### Two statements about reopening, and a message left alone

`reopen_complaint` accepts `resolved` **and** `closed` while its error message and `API.md` said only
resolved. The first instinct — widen the message — was wrong: both statuses render as `Resolved` on
the wire, so a message naming `closed` would describe a state the resident's screen never shows. The
message stands; the SQL comment now says which statuses it means and why the wording differs, and
`API.md` records the asymmetry the frontend actually needs — a complaint already confirmed can be
reopened but not re-confirmed, so *both read `Resolved` while only one offers confirm*. `DERIVED`.

### API.md

- §7 `GET /complaints`: `status` documented as matching on what a complaint **displays as**.
- §7 `GET /complaints/{id}`: `hasOlderEvents` / `hasOlderComments`, `label` on a timeline entry, and
  the paragraph on why the bound keeps the recent end.
- §7 `/reopen`: the reopen/confirm asymmetry, and why `Cancelled` is excluded.
- §7 `/read`: the view reads the caller's marker, not the raiser's.
- A claim in `GET /complaints/{id}` that internal comments were filtered by the policy *and not by
  this API* — the repository does filter as well. Corrected rather than deleted; the policy is still
  what makes it true.

### ERD

`complaint_overview`'s note now states which membership the read-state join matches, and why.

---

## 2026-08-04 — Session 34: the first water in the pipe

**Context.** Step 4 of `RESIDENT_BACKEND_DESIGN.md` §9 — the resident complaint surface, and the
notifications every complaint write now emits. `0031_resident_complaints.sql`, six new operations, and
two of `0020`'s functions replaced. Also, the one item left over from step 2.

### The step-2 leftover: a bound that truncated silently

`GET /amenities/available` read under a 500-row bound and returned `hasMore: false` unconditionally.
Those two facts cannot both be safe. The bound is real — it exists so a pathological community cannot
page a whole view into memory — so a permanent `false` was the envelope asserting completeness it had
never checked, in the one situation where a client has no way to detect the difference. The read now
asks for an exact count alongside the bound, and `hasMore` means the one thing worth meaning: the
catalogue has outgrown being unpaged. **The number is not expected to be reached; that is not an
argument for leaving it unmeasured.** `AUDIT`.

### The migration number, and why it is not 0025

`0025` was free and would have been wrong. Every RPC in this file calls `notify_member`, `0030`
creates it, and migrations apply in filename order — so a file numbered `0025` would run five files
before its own dependency. **Postgres would not have objected**: a plpgsql body is not resolved
against the catalogue until it executes, so the migration would have applied cleanly and failed at the
first complaint. Session 32 retired *reserve a number in advance*; this is the other half of the same
rule — *allocate at write time* does not mean *take the smallest free one*. `DERIVED`.

### `complaints` had no row security, and this is the step that makes that matter

`0020` enabled RLS on `complaint_events` and `complaint_comments` and left the parent table open. Any
authenticated user could read every complaint in the project through PostgREST. That was survivable
while complaints were an admin surface reached through an admin-guarded API; **this step is what puts
a resident's grievances behind an endpoint they call themselves**, so the policy ships in the same
file. The same timing rule as `0028` and `0030`, for the third time.

The two child policies were tightened at the same time. They used `is_community_member`, which would
have let any resident read a neighbour's complaint timeline the moment residents had a reason to look.
Admins see the queue; a resident sees their own. `AUDIT`.

### `resolved` and `closed` stop being synonyms

The baseline's enum has carried both since the beginning and nothing used the distinction —
`PATCH /complaints/{id}` treats them as one terminal state. `POST /complaints/{id}/resolution` gives
the second one meaning: **the association resolves, and only the resident closes.** That is what
`US-2.6`'s *"confirm resolution with a rating"* is actually asking for, and it needed no new column to
express. `DERIVED`.

### Two of `0020`'s functions were replaced, not wrapped

The complaint events a resident most needs to hear about are the ones an **admin** causes, so
`update_complaint` and `add_complaint_comment` gained a `notify_member` call inside the transaction
they already had. §7 of the design says a notification retrofitted onto a working write path is how
you get an event that fires for some callers and not others — which is precisely the argument for
replacing the one writer rather than adding a trigger or a second path. `DERIVED`.

Two rules were set here that every later emitter inherits. **A status change notifies; an assignee or
a progress bar does not** — a resident notified about everything stops reading notifications, which
costs more than the ones they miss. And **an internal comment notifies nobody**, for the same reason
it now leaves no timeline row.

### An internal comment was casting a shadow on the resident's timeline

Found while writing the API.md section, not while writing the code. `0020` writes a `comment_added`
event for *every* comment, internal ones included, because the timeline it was written for is
admin-facing — and the policy on `complaint_events` scopes rows to the complaint, not to a comment's
visibility. So the resident's new timeline would have shown a row saying something was said, with
nothing to read. **That is a worse outcome than showing the comment**: it tells them they were
discussed and refuses to say how. `GET /complaints/{id}` drops those events. API.md §7 previously
claimed internal comments were "never written to the timeline"; that claim was wrong and is corrected
in place rather than deleted. `AUDIT`.

### Stories

US-2.5 **none → served**, US-2.6 **partial → served**, US-2.8 **partial → served**. Resident coverage
moves from 0 served / 8 partial / 4 none to 3 / 6 / 3.

**US-2.7 stays partial, deliberately.** Its emitters now exist — every transition the story names
writes a notification, and both transports carry it. What is missing is a service worker in
`frontend/public/`, so no phone can receive one. Marking it served would be reporting software this
repository does not contain.

Two items on §14.7's list closed by different means, and only one is a fix: item 3 (`complaints.priority`)
was **built**; item 1 (the snapshot dropping `assignee`, `dueAt`, `progress_percent`) was **routed
around** — the fields now reach a resident through a different endpoint while the projection that drops
them is unchanged, and it is still two lines in the dashboard workstream's file. Recorded as such,
because a matrix that marked item 1 done would be recording the story's state as if it were the code's.

### Artifacts

- **`docs/API.md`** — §7 rewritten: the six resident operations, the two vocabularies, the
  notification note, and the correction above. §14.2 recounted, §14.4 US-2.5/2.6/2.7/2.8 rewritten
  with the old assessments left in place beneath their closures, §14.6 recounted from the spec
  (**41 mapped + 43 unmapped = 84**, Feature 16 → 17), §14.7 items 1 and 3 struck through.
- **`docs/ARCHITECTURE.md`** — new *Who writes into it* subsection: the emitter table, the fan-out
  helper, and the two notification rules.
- **`docs/diagrams/homebandhu_submission_erd.dbml`** — the `0031` columns, `complaint_overview`, and
  **the `0019`/`0020` complaint columns, which had been missing from this diagram since those
  migrations** — a pre-existing omission, this file's rather than the schema's.
- **`docs/diagrams/HomeBandhu-Architecture-Classes.puml`** — the resident complaint router, service
  and repository; five RPCs; the dependency from the admin router to the replaced functions.
- **`docs/design/RESIDENT_BACKEND_DESIGN.md`** — step 4 marked done; §7's complaint block promoted to
  a written migration with the four unanticipated additions recorded; the numbering constraint stated
  where it would have been broken.
- **`backend/supabase/migrations/README.md`** — `0031` row, the second half of the numbering rule,
  recounted at **14 views and 54 functions**, 41 called from Python.

---

## 2026-08-04 — Session 33: something can finally reach a resident who is not looking

**Context.** Step 3 of `RESIDENT_BACKEND_DESIGN.md` §9 — the notification substrate, the feed, Web Push
registration and the sender. `0030_notifications.sql`, six new operations, and the first runtime dependency
this workstream has added.

**What it closes, and what it does not.** Three stories — US-2.1, US-2.4, US-2.7 — have been *Partial* for one
shared reason: the event fires and nothing delivers it. That is now a transport that exists. **It is not three
closed stories, and saying so would be reporting a pipe as water.** Nothing emits into it yet: the visitor
pass, the complaint transition and the published notice each need one `notify_member` call inside the write
that causes them, and those writes are steps 4 to 6. The difference the step made is that each is now a task
rather than an architecture decision — which is exactly what `API.md` §14.7 item 7 said it was.

**`docs/API.md`** — §5 gains two subsections; §14.4, §14.6 and §14.7 corrected — `DERIVED`, and one `AUDIT`.

§5 is retitled *Live updates, notifications and the admin dashboard*. The heading had been kept only to avoid
renumbering; it now has a second job, because §5.1–§5.3 are the three delivery layers of one design and
keeping them together is worth more than a heading that names one of them. No section numbers moved.

The entry worth reading is the rule §5.2 opens with: **the stream is not the notification system.** SSE is
at-most-once and connection-scoped — §5.1 makes *the payload is a hint, never truth* load-bearing, and it is
only safe *because* of that rule — and a push may simply not arrive. So the row is written first, inside the
transaction that caused it, and both transports carry it. Nothing durable can be built on `sse_events`: it is
pruned every fifteen minutes precisely because it is ephemeral.

§5.3 records the `PO` ruling from Session 31's design work in the reference doc where a frontend developer
will meet it: **the push body carries the detail**, because US-2.1's pain point is a notification that makes a
sound and shows nothing, and a resident being asked to approve someone needs the name. With the one absolute
exception — **the visitor security code may never appear in a push body** — and the note that this is enforced
by construction rather than by review: the renderer reads `title`, `body` and `url` and copies no other key.

The `AUDIT` is in §14.4 and §14.7. Three story sections and one action item asserted *"no push transport at
all"*, which stopped being true in this session. The old text is left in place with the correction beneath it
rather than rewritten, for the same reason §3.1 of the design doc keeps its present tense: it is the argument
that produced the work. §14.6's totals are recounted from the spec — **36 mapped + 42 unmapped = 78** — and the
`Feature` count moves 14 → 16.

**A design-document claim that had already gone stale** — `AUDIT`.

§6 of the design says the seven live-update endpoints *"will be annotated `x-no-user-story` … except
`GET /notifications`"*. `GET /events` was annotated against **US-1.3** in Session 29, so the sentence was
wrong before this session started. Annotated accurately — two stories-bearing operations in that table, not
one — and recorded here rather than fixed silently, because a count nobody re-derives is the kind of claim
that decays.

**`backend/supabase/migrations/0030_notifications.sql`** — the substrate — `DERIVED`.

Four things the design's §7 list did not anticipate, all of them consequences of `notifications` being written
for the first time:

- **Row-level security on `notifications`, with a read policy.** The table is reachable through PostgREST and
  had none, so any authenticated user could read every notification in the project — complaint updates,
  visitor names, invoice amounts. Nothing exploited it because nothing wrote the table. **This migration is
  what starts writing it**, so the policy lands in the same file: the same timing rule as `0028`, where the
  fix ships before the thing that makes it exploitable.
- **`is_own_membership(uuid)`**, the third shared RLS predicate beside `0019`'s two. §5.2 of the design says
  ownership is enforced in SQL rather than in Python; this is the function that lets it be.
- **Reads get a policy, writes get none.** Marking read is therefore a SECURITY DEFINER function, which is the
  better shape anyway: knowing a notification id is not enough to mark someone else's read.
- **`push_subscriptions` is `service_role` only**, so registration cannot be a PostgREST insert. Both
  subscription functions check `is_own_membership` first — a SECURITY DEFINER function that trusts a
  caller-supplied membership id is one that lets anyone subscribe a device to anyone else's notifications.

**The sender obeys a rule the SSE hub does not** — `DERIVED`.

> The hub may drop. The sender may not duplicate.

The hub tolerates several processes: each polls on its own cursor and fans out to its own connections, so two
workers means two harmless copies. Two senders reading one unsent notification means a phone that buzzes twice
for one visitor. Claiming is therefore atomic in the database — `for update skip locked` inside
`claim_push_batch` — and the row is marked sent **before** the HTTP call, so a crash loses a buzz rather than
repeating one. At-most-once is the correct bias for something that vibrates a phone at night, and the
notification is in the feed either way.

Two things the build decided that §10.4 had not. The sender starts from the **application lifespan**, not
lazily like the hub — it exists to reach someone with nothing open, so a sender that waited for a connection
would only run when it was not needed. And **nothing retries a send**: a transient failure increments the
subscription's counter and the *next* notification is the retry, because retrying one against a struggling
push service is how a backlog becomes a herd.

**The VAPID keypair, and what this workstream did not do** — `PO`, restated because it matters.

`PushSettings` is a second `pydantic-settings` class reading the same `.env`, so `app/config.py` — the auth
workstream's file — is untouched. `.env.example` documents the three variables as optional.
`backend/scripts/generate_vapid_keys.py` prints three lines to stdout and writes no file.

**No real key was generated, held or seen while building this.** The script was exercised in a way that
reported only the *shape* of its output — lengths and character class — and never the values. The tests use
strings shaped like keys that sign nothing. One thing the build added: `configuration_problem()` returns prose
for a log line and never echoes the value it rejected, because half a private key in a log file is a leaked
private key.

**Honest scope** — `AUDIT`.

Push ships **backend-complete and unverifiable end to end.** `frontend/public/` holds a favicon and an icon
sprite: there is no service worker, no manifest, and no resident page opens a connection of any kind. So no
push can be *observed* arriving. What the 52 new tests cover is registration and idempotency, payload
construction, the `410`-prunes-the-subscription rule, the per-subscription isolation of failures, and the
configuration gate — with the call to the push service mocked. That is honest coverage of this half and is
described that way in `API.md` §5.3 rather than left for someone to discover.

**A new runtime dependency.** `pywebpush>=2.0`, the first this workstream has added to `dependencies` rather
than to `dev`. It brings `py-vapid`, which the key script uses. The alternative was implementing RFC 8291
encryption by hand, which is not a thing to hand-roll.

**`docs/ARCHITECTURE.md`, the ERD and the class diagram** — all three updated, and one of them found a
pre-existing gap — `DERIVED`, plus one `AUDIT`.

`ARCHITECTURE.md` gains *Out-of-app delivery: notifications and Web Push*, beside the live-updates section
rather than inside it, because the point being made is that **the stream is not the notification system**.
It carries the transport choice with its rejected alternatives, the sender's non-duplication rule, the four
limits worth knowing before someone rediscovers them (4 KB payloads, `410` prunes, iOS needs an installed PWA,
rotation is silent), and the fail-closed configuration behaviour. `notification.created` is added to the topic
table.

The ERD gains `push_subscriptions`, the two new columns and indexes on `notifications`, and the two new views.
**The `AUDIT`:** `sse_events` was still documented without the three columns `0028` added in Session 29 — the
migration landed and the diagram did not. Corrected in the same pass, and the entry is the reminder that a
diagram is only as current as the last person who thought to open it.

The class diagram gains a resident package: four routers, three services, three repositories, `PushSender`,
`PushSettings`, and the `0029`–`0030` schema, with the relationships that matter — `PushService` renders
*through* `NotificationsService`, and `notify_member` is the only writer of `notifications`.

**Not changed.** `app/config.py`, `app/api/deps.py` and anything else in the auth workstream's territory.
`frontend/src/` — untouched, as always; what it must add for any of this to be visible is listed in the design
doc §10.6 rather than built here.

---

## 2026-08-04 — Session 32: the `[~]` becomes a tick, and the numbers stop being promises

**Context.** Two things left standing at the end of step 2, fixed before step 3 rather than after it.

**The divergence is closed, and the reason it could be is a scheduling one** — `PO`, overturning
Session 31.

Session 31 recorded `bookable_amenity` as "worth doing when a second resident reader appears".
That deferral rested on a schedule argument, not a design one: writing the view would have made the
schema change of a step whose entire premise was *this needs no migration* non-zero. **That argument
expires the moment the next step needs a migration anyway**, and step 3 does. So the view was written
first, and the checklist item that read `[~] Reads through views` is a tick again.

`0029_bookable_amenity_view.sql` is two views over one table, each owned by the surface that reads
it. It carries the resident column list, applies the row filter — active, no temporary closure — and
is `security_invoker` like every other view here. *Bookable* is now defined in one place rather than
assembled by whoever writes the query. §12 keeps the whole argument, including the version of it that
was true for one step, because a checklist that quietly rewrites its own history is not evidence of
anything.

**One duplication was kept on purpose, and it is the interesting part.** The service still applies
the temporary-closure test in Python, on a column the view exposes and has already filtered on. The
reason is stated in the migration and in §12: **no migration in this project has been applied to any
database yet**, so the view's predicate has never executed, while the service's has tests behind it —
and the endpoint should not depend on which of the two is true. The SQL is written as an exact
transcription of the Python test, every `jsonb` value `bool()` reads as false spelled out, because
two readers disagreeing about whether the pool is shut is worse than either answer alone. When the
migrations are applied, the Python pass is the half to drop.

**The design doc stops naming migration files that do not exist** — `DERIVED`, from Session 30.

Session 30 replaced per-file number reservations with per-workstream *ranges*, on the argument that
reserving a number binds a filename to work whose shape is not yet decided. §7 and §9 were left
naming a file per planned schema change, which is the same mistake in a different document — and it
had already gone wrong twice: step 2 was planned with a migration and shipped without one, then the
view took `0029`, which §7 had reserved for notifications.

So §7 now names only the files that exist and describes the rest as schema changes, and §9's steps no
longer carry a number each. The ordering constraint that actually matters is stated instead of
implied by the numbering: **the notification substrate comes before the feature migrations**, because
every feature RPC calls `notify_member(...)` and a notification retrofitted onto a working write path
is how you get an event that fires for some callers and not others.

**`backend/supabase/migrations/README.md`** — `0029` added to the table, view count `11` → `12`. The
paragraph on numbering now uses `0029` as the worked example of the rule: it was drafted as the
notification migration, that step has not been written, and the number went to the file that was.

**`docs/API.md`** — the §10 entry now says the read goes through `bookable_amenity` and that the view
applies the row filter as well as the column list. The tenancy paragraph gains one clause: the view
is `security_invoker`, `amenities` carries no RLS policy, so it inherits nothing and the
`community_id` filter is still the entire boundary.

**Not changed.** `docs/openapi.yaml` — regenerated, still 63 paths / 72 operations and no drift,
which is the expected result: the response model, the guard and the error set are untouched, and a
change of storage that moved the spec would have meant one of them had leaked into it. `ARCHITECTURE.md`
— a second view over an existing table is not a new mechanism. The ERD and class diagram — no table,
column or class changed; `bookable_amenity` is a projection of `amenities`, and an ERD that grew a
box per view would stop being an ERD.

---

## 2026-08-04 — Session 31: the resident can finally see what they were already allowed to book

**Context.** Step 2 of `RESIDENT_BACKEND_DESIGN.md` §9 — `GET /amenities/available`. No migration,
which was the point of putting it second: it makes an endpoint that already ships usable, at zero
schema cost.

**What §3.1 was.** `POST /amenities/{id}/bookings/request` has never carried an admin guard — it was
written for residents and its docstring says so. But the amenity catalogue reached a client exactly
once, inside `GET /dashboard/snapshot`, behind `require_membership_role('admin', 'manager')`. So the
product contained a write path a resident was entitled to call with an argument they had no
entitled way to obtain. Not a security hole; worse in a mundane way — **a feature that could not be
used.** It happened because the amenity work was built outward from the admin screens, which get
their catalogue from a snapshot they were already fetching, so nobody ever needed a list endpoint
and the resident half inherited the absence.

**`docs/API.md`** — §10 gained the endpoint; §1.4 and §14.6 recounted — `DERIVED`, and one `AUDIT`.

The endpoint entry states the thing its name does not: **"available" means bookable in principle,
not free right now.** Every row is active with no temporary closure. Whether a *slot* is free is
decided on write under an advisory lock by the booking guard, which is the rule the rest of §10
already follows — *no availability check happens in the API* — and a read endpoint that answered it
would be describing a moment already past by the time the resident submitted.

The `AUDIT` is in §14.6, and it is a counting one. The section read *"36 of the 70 operations map to
no story"*; the surface is now 72 operations, 35 mapped and 37 not. The totals had already drifted
when `GET /events` landed in Session 29 and were not corrected then. They are now taken from
`x-user-stories` in the generated spec rather than derived by hand — the same lesson the section's
own earlier correction records, applied to itself. §1.4's *"every one of the 70 operations"* was
rewritten to state the guarantee rather than a number, since the exporter enforces it per operation.

**`docs/design/RESIDENT_BACKEND_DESIGN.md`** — §3.1 closed, §9 step 2 done, §12 amended — `DERIVED`.

§3.1 keeps its present tense and gains a *Closed* note, as §3.5 did: the argument that produced the
endpoint is worth being able to read as it stood. The note records the two things decided during the
build that the section had not covered — excluding temporarily closed amenities, and returning the
catalogue unpaged.

**§12's coherence checklist has its first item that is not a clean tick, and that is the entry worth
reading.** *"Reads through views"* is now `[~]`, because this read goes to the `amenities` table.
The available view, `amenity_overview`, exists to give the admin card two lateral aggregates this
response discards — and, more to the point, reading it would leave the resident projection one
column away from an admin field, since the next column added to that view for the admin card would
immediately be in scope here. §3.1 is a finding about precisely that failure. The fix that would
make it a clean tick is a `bookable_amenity` view, and it is recorded as worth doing when a second
resident reader appears; inventing one now would have given a step whose whole premise was "no
migration" a migration, for a cosmetic reason.

**A new `x-no-user-story` category, and an honest reason** — `AUDIT`.

The endpoint traces to no user story, and `catalogue_read` says why in a way the existing
`catalogue` entry could not: that one covers amenity *upkeep*. No interviewee described the act of
finding out which amenities exist, because in the building that is a noticeboard. §14.6 now uses it
to make a point the table had been carrying implicitly — **a `Feature` row is not always a story
someone forgot to write; sometimes it is one nobody could have written.** This gap surfaced from
reading the code, and no amount of reading the story set would have produced it.

**Not changed.** `ARCHITECTURE.md` — the endpoint introduces no new mechanism, transport or trust
boundary, and adding a row for every route would turn a wiring document into a second API reference.
The ERD and class diagram — no table, column or class changed.

---

## 2026-08-04 — Session 30: housekeeping between steps, sorted by who owns the file

**Context.** Step 1 left a handful of loose ends. Rather than open a cleanup session for them, they
were sorted by a single question — *who else can edit this?* — because that, not severity, decides
what shape a fix can take. Items in files this workstream owns are fixed inline. Items in shared
files get one small commit each so a merge conflict is one hunk. Items in another workstream's
semantic territory are **not fixed at all**; they are documented or handed off, because a silent
change to someone else's runtime behaviour is worse than an open item.

**`backend/supabase/migrations/README.md`** — number reservation replaced with number ranges —
`DERIVED`.

The file previously reserved `0025`–`0027` and `0029`–`0030` for specific planned resident
migrations. That binds filenames to work whose shape is not yet decided: step 2 of §9 turns out to
need no migration at all, so the reservations were already drifting one step into the build. Ranges
are now reserved per workstream (`0018`–`0024` admin, `0025`–`0039` resident) and a number is
allocated to a file when the file is written. Clash avoidance is unchanged — a workstream still only
takes numbers from its own range — but reordering or dropping a step no longer makes this file
wrong. Nothing requires contiguity; only filename order matters, which is why `0028` shipping before
`0025` exists is not a problem to be tidied.

**`docs/API.md`** — §1.5 gained a paragraph on the `422` over-declaration — `AUDIT`.

`422` is declared on nearly every operation in `openapi.yaml` while `api_annotations.py` traces it
to a specific validation rule on roughly half that many. The source is `app/main.py` declaring it
once on the whole `include_router(...)`, so every route inherits it. **This is deliberately not
being fixed.** Fixing it means either editing the application shell — another workstream's file —
or teaching the exporter to subtract a claim the running app makes, which would let the spec
contradict the app and is a worse property than over-promising. It is also not false: FastAPI
returns `422` from any operation with a parameter it fails to coerce. So the document now explains
the two readings instead: the per-endpoint tables list validation done *on purpose*, the spec lists
where a `422` is *reachable*. This closes the item as documented rather than as fixed.

**`backend/pyproject.toml`** — `pglast>=6.0` added to the `dev` extra — `AUDIT`.

The migrations README claims every migration is validated with `pglast`, but it was not declared
anywhere, so the claim depended on whoever last ran the check having installed it by hand. It is now
installable from the project file like `pyyaml`, which is in there for the same reason: a tool a
documented process depends on belongs in the manifest.

**Not changed, and deliberately.**

- **No trigger on the tables `0018`–`0023` added.** The non-invasive form exists — a new migration
  extending `0007`'s `to_regclass`-guarded loop, with no edit to `0007` itself. It is still not
  written, because those tables belong to the admin workstream and adding triggers changes how often
  *their* dashboards refresh. It also acquired a dependency `0007` never had: after `0028`, any new
  trigger must declare an audience. Handed off rather than done.
- **The `update` closing `0028`.** Flagged in Session 29 as the file's one non-additive statement.
  Kept. It is idempotent — its `where` clause matches nothing on a second run — and splitting it into
  its own file would allow the schema to be applied without the repair it exists to perform.
- **`requires-python = ">=3.10"`.** Previously recorded here and in session notes as *false*. That
  was an over-claim and is corrected: there is no 3.11+ syntax in `app/`, `scripts/` or `tests/`, and
  `uv.lock` resolves at `>=3.10` with nothing forcing higher. The accurate statement is that the 3.10
  floor is **declared but never exercised** — the only interpreter anyone runs is 3.13 and there is
  no CI. Left alone pending a ruling, since raising it changes a shared file on the strength of a
  preference rather than a defect.

---

## 2026-08-04 — Session 29: the first resident step ships, and a disclosure closes

**Context.** Step 1 of `RESIDENT_BACKEND_DESIGN.md` §9 — `0028_event_audience.sql`, the audience
filter in the realtime hub, and `GET /events`. It is first in the build order because it is the only
item on the list that is a **defect in code that already ships** rather than a feature that is
missing, and because every later step points more clients at the stream it affects.

This is the first session in which the resident design stops being purely a document. That changes
how the design file must be read, so the status markers are part of this entry rather than an
afterthought.

**What the disclosure was (`AUDIT`, recorded in Session 28 §3.5, closed here).** `GET
/dashboard/events` is guarded by `get_active_membership` — *any* active member, never an admin role —
and the hub fanned out on `community_id` alone. Every subscriber in a community therefore received
every event in it, including `0024`'s `access_request.created`, which carries a neighbour's name,
their requested relationship and the community's pending count. Nothing exploited it because no
non-admin client connected to anything; the resident portal is what would have made it exploitable,
which is the whole reason this step comes before the portal rather than after.

**`docs/API.md`** — §5.1 retitled and rewritten; §14 US-1.3 corrected — `DERIVED`.

- §5.1 is now *Live updates — `GET /events`*, with `GET /dashboard/events` documented as a deprecated
  alias of the same handler. Adds the audience table, the rule that the filter runs on values
  resolved out of Postgres rather than anything client-supplied, the `stream.resync` topic, and an
  explicit statement that a resident does not get a blanket refresh frame.
- The §14 US-1.3 entry said *"the stream serves the admin portal only"*. That was wrong in a way
  worth naming: it described a live disclosure as a missing feature. Corrected in place with a
  visible `> **Correction.**` block, per the convention in `docs/design/README.md`, because the
  reasoning that produced the wrong sentence — *the path says `dashboard`, so the audience must be
  admins* — is exactly the reasoning the next reader is liable to repeat.
- US-1.3 stays **partial**. `0028` fixes the transport, not the consumers: there is still no resident
  client subscribed and no resident-facing topic to subscribe to, and reports are still computed per
  request rather than pushed.

**`docs/ARCHITECTURE.md`** — new *Audience scoping* subsection; Topics table gains an audience
column; transport row and sequence diagram renamed to `GET /events` — `DERIVED`.

- The *Guarantees and limits* reconnect bullet now records that the backfill filters **twice**, and
  why that is not redundancy: the query is capped at 100 rows, so filtering only in Python would let
  a burst of admin traffic fill the page and hide a resident's own events behind it, while filtering
  only in the query would put a security decision in a hand-written PostgREST string. Together, a
  mistake in that string loses an event and cannot leak one.

**`docs/design/RESIDENT_BACKEND_DESIGN.md`** — status markers, §3.5 closure note, §9 status column,
§10.2 extended — `DERIVED`.

- Header changed from **Status: proposed** to **Status: in build**, and says that where a section
  describes something now built, the code is the authority and a disagreement is a bug in the
  document. Per-step status lives in the §9 table and nowhere else, so there is one place to update.
- §3.5 gains a *Closed* note but keeps its present tense. A finding rewritten as though it had never
  been true is how the same mistake gets made a second time.
- §9 gains a status column, and the note that **done means merged, tested and documented — not
  written** — and that whether a migration has been *applied* is a separate question again, still
  answered *no* for every file including `0001`.

**Two things the build added that the design had not anticipated** (`DERIVED`, both recorded in
§10.2):

- **A shape `check` constraint, not just a default.** `sse_events_audience_shape_check` makes the
  three audiences mutually exclusive and complete; the reader independently fails closed on anything
  it cannot classify. Either half alone is worse than both — a fail-closed reader with no constraint
  turns a malformed row into a silent non-delivery, and a constraint with a permissive reader means
  that the day a fourth audience value is added, every older process treats it as community-wide. The
  pair is what makes a bad row *unwritable* rather than *undeliverable*.
- **The resync frame needed a topic per role.** A connection that falls behind is told "you have a
  gap, re-read". The admin frontend already listens for `dashboard.refresh` and this workstream does
  not edit frontend code — but `0028` retargets that *topic* to `{admin,manager}`, so sending it to a
  resident would contradict the migration in the same breath as writing it. The synthesised frame is
  therefore `dashboard.refresh` for an admin or manager and `stream.resync` for every other role: one
  instruction, two names, chosen from the subscriber's verified role. Any resident client must handle
  `stream.resync` — it is the only frame that arrives with no domain event behind it.

**`backend/supabase/migrations/README.md`** — `0028` listed; `0025`–`0027` and `0029`–`0030` marked
reserved with the reason the numbering is out of order; the "none applied yet" line strengthened to
say **including `0001_baseline.sql`** — `AUDIT`. That fact was true and stated elsewhere, but the
sentence a reader lands on first read as though only `0018`–`0024` were unapplied.

**One decision worth flagging as mine to overrule.** `0028` ends with an `update` that retargets
rows *already* in `sse_events` for the three admin topics. Without it, the disclosure would persist
for the length of the retention window — `prune_sse_events` keeps two hours — after the migration
ran. It is the one non-additive statement in the file. It touches only rows the same migration is
about, and on an unapplied database it matches nothing at all.

**Not changed.** No frontend file. No auth-workstream file. `docs/openapi.yaml` was regenerated by
`scripts/export_openapi.py`, never hand-edited; the exporter's two-way guard failed the build twice
during this step — once for an unannotated operation, once for a stale checked-in spec — which is the
behaviour it exists for.

---

## 2026-08-04 — Session 28: four rulings, one of which reverses a default this document set

**Rulings (`PO`).** Four answers to open questions in `RESIDENT_BACKEND_DESIGN.md` §8, plus an
instruction to give the design folder a README.

**`docs/design/README.md`** — new (`PO`).

- The folder had two documents and no explanation of what it was. The README states the split the
  folder exists for — every other document under `docs/` answers *what*, these answer *why* — and
  why that needs its own home: the *what* documents regenerate or fail loudly when they are wrong,
  and nothing at all breaks when a reason is lost. It records the shared shape of both documents, the
  conventions they follow (state the cost; cite `file:line`; correct in place with a note rather than
  silently; separate decided from defaulted), and the five artifacts a new design is checked against
  before it is written.
- It also names the difference a reader has to know: `ADMIN_DASHBOARD_DESIGN.md` is retrospective and
  can be checked against code, `RESIDENT_BACKEND_DESIGN.md` is prospective and none of its §6 exists.
  Neither is evidence of what runs.

**`docs/design/RESIDENT_BACKEND_DESIGN.md`** — §5.5 rewritten, new §11, §10.5 rewritten, new §10.8,
§8 Q2/Q3/Q6/Q8 answered, and consequent edits to §6, §7 and §9. Checklist renumbered §11 → §12.

- **§8 Q2 — `checked_in` is terminal (`PO`).** Default confirmed, not changed. Recorded with the
  reason rather than just the answer: once the guest is through the gate, "cancel" is a physical-world
  operation and no database write performs it, so allowing the transition would produce a record that
  disagrees with what happened. Enforced in the RPC with a stable `pass_already_used` code, not in the
  service — the invariant lives next to the data.
- **§8 Q6 — the push body carries full detail (`PO`). This reverses the default this document set,
  and the default was wrong on the requirements rather than merely over-cautious.** `US-2.1`'s
  recorded pain point is *"notifications sometimes produce only a notification sound without
  displaying the actual notification"*; a generic *"Visitor at the gate"* is a milder version of the
  exact failure the story exists to fix. The privacy objection also does not survive contact with the
  protocol: RFC 8291 encrypts the payload end to end keyed to the subscription, so the push services
  relay ciphertext they cannot read — which is precisely the property §5.11 bought by rejecting
  OneSignal, and having paid for it we should use it.
- **§10.8 (`DERIVED`).** New section: what a push actually carries. One hard exclusion — **the visitor
  security code may never appear in a push body**, because §5.4 makes it a hashed credential returned
  once and a credential on a lock screen is readable by anyone holding the phone. Also bounds "all
  details" by what a web push can actually render (`PO`: *"this is not a push like the one we have in
  a native app"*): title, body, `tag` for coalescing, `data` for the deep link, and at most two
  actions which iOS does not show — so the flow never depends on them.
- **§8 Q8 / §10.5 — the VAPID keypair (`PO` asked for the most secure option that fits the framework).**
  Answered: environment variables through a second `pydantic-settings` `BaseSettings` class, one pair
  per environment, held by whoever holds that environment's `SUPABASE_SERVICE_ROLE_KEY`. The argument
  is that the environment is already this application's trust root and holds something strictly more
  dangerous — the service-role key bypasses RLS on every table, where the VAPID private key only signs
  pushes to endpoints stored in a `service_role`-only table. Putting the weaker secret behind a
  stronger mechanism while the stronger one stays in `.env` adds a moving part and moves no risk.
  Four alternatives rejected in a table, one of them (generate at boot) as broken rather than
  inelegant: `applicationServerKey` is baked into every subscription, so a regenerated key silently
  kills all of them.
- **§10.5, corrected (`AUDIT`).** Session 27 said the config module this workstream must not edit is
  `app/core/config.py`. It is `app/config.py`. The boundary it describes is unchanged and the
  separate-settings-class decision still holds — and it holds for a better reason than was known then:
  `Settings` is configured `extra="ignore"`, so a second class reads the same `.env` with no edit to
  the first.
- **§10.5, new (`DERIVED`).** Two operational facts that were missing. Push fails *closed but quiet* —
  no keys means `push_enabled = False`, the sender does not start, the two push endpoints return 503
  `push_not_configured`, and nothing else in the product degrades, the same shape as `0024` no-opping
  when pg_cron is absent. And rotation is an incident, not hygiene: it unsubscribes every browser
  silently, the protocol offers no dual-key period, and the only mitigation is a client-side key
  comparison on load, now listed in §10.6.
- **§5.5 rewritten and §11 added — the payment gateway is a simulator we build (`PO`).** *"It is not
  an actual payment; any payment will pass, with a few cases like a card past its expiry triggering a
  payment failed, to show we can handle that too and maintain business logic."* This supersedes
  §8 Q3, which asked whether the endpoint should exist before a gateway did.
  - **§11.1 (`DERIVED`).** `provider = 'simulator'`, and this is the decision everything else rests
    on. A demo database becomes a staging database becomes something somebody reconciles; if
    simulated payments are written as `'offline'` or under a real provider's name, then on the day a
    real gateway lands **nobody can separate the money that moved from the money that did not**, and
    the information to do so was never recorded. It also gives the honest form of the rule §5.5 has
    carried since the first draft: the row says `succeeded` *and* says which gateway said so.
  - **§11.3 (`DERIVED`).** The simulator accepts published test cards only and rejects anything else
    with `card_not_supported`. A mock gateway that accepts any Luhn-valid number *will* be handed a
    real card — by a tester being thorough or a demo audience being helpful — and at that moment we
    are an application holding a live PAN with none of the obligations discharged. Closing it by
    construction beats a warning nobody reads, and it costs nothing against the brief: the same test
    card passes with a future expiry and fails with a past one, which is the demonstration asked for.
    Nothing card-shaped is stored, logged or echoed; the fields are `SecretStr` so a stray `repr()` in
    a traceback prints asterisks.
  - **§11.5 (`DERIVED`).** A declined payment is `200` with a `status` field, not `402`. The request
    was well-formed and produced a durable record; the *payment* failed. Making it an error would put
    an ordinary business outcome in the same client branch as "your session expired", and leave the
    payment id nowhere sensible to live.
  - **§11.6 (`DERIVED`).** The simulator is a pure function in one module, sitting exactly where a
    real gateway will sit, with the settlement RPC unchanged either way. The argument for building it
    properly rather than stubbing a success: the failure paths are the ones that are hard to exercise
    against a real provider, and they are the ones `US-2.12` is about.
  - **§11.7 (`AUDIT`).** `US-2.12` is about the transaction, not the gateway. Its pain point —
    *"payments can fail even after money has been deducted"* — describes a payment recorded in one
    transaction and a booking confirmed in another. So the failure branch is specified as explicitly
    as the success branch: a failed payment writes its row, leaves the booking untouched, and never
    enters a balance, because every recomputation sums `succeeded` rows only.
- **§6 (`AUDIT`).** `POST /amenity-bookings/{id}/pay` added. `US-2.12` is the only user story about
  payment and it is about **amenity-booking** payment; an invoice-only path would have left it
  untouched while appearing to serve it. Second caller of one simulator, not a second system.
- **§6, corrected (`AUDIT`).** The endpoint total in §6 has been wrong since Session 26. The prose
  said 19 feature endpoints and 26 total; counted from the tables it was 21 and 28, and it is 22 and
  29 after the addition above. Session 27's entry below inherits the wrong figure and is left as
  written — it records what was believed at the time. The cause is worth more than the number: a
  count kept in prose next to a table nobody re-derives it from. Corrected in place with a note, so
  the next person to add a row sees that the failure mode exists.
- **§7.** `0030_payment_simulation.sql` added — `failure_code`, `instrument_label`, and the two
  settlement RPCs. Explicitly **no new index**: the baseline's `unique (community_id,
  idempotency_key)` is already the right constraint, and what was missing was a stated rule about who
  mints the key. §11.4 states it — one key per press of Pay, a new key for a new attempt after a
  shown decline. The key identifies an attempt, not an invoice; backwards, it produces either a double
  charge or an unpayable invoice.
- **§9.** Step 6 absorbs `0030` and the simulator rather than splitting it, because splitting would
  separate the two halves of one transaction across two shippable units — the exact thing `US-2.12`
  is about not doing. Also states explicitly that spec regeneration, the `api_annotations.py` entry
  and the `API.md` section are **part of each step**, enforced by the exporter's two-way guard, and
  that step 8 is the traceability-matrix pass rather than a catch-up for skipped documentation.

**`docs/design/ADMIN_DASHBOARD_DESIGN.md`** — two edits.

- Header links the new folder README.
- §9 gains a row: **taking money was never in scope.** `record_payment` is offline reconciliation with
  `provider = 'offline'` and must not be mistaken for a gateway. Added because a reader who now knows
  a simulator exists will go looking for it in the wrong document, and because the two provider values
  are what keep the distinction permanent.

---

## 2026-08-03 — Session 27: live for everyone, which turns a latent flaw into the first task

**Ruling (`PO`).** *"All updates are supposed to be live across all users. The push notifications are
to be implemented too."* This closes open question 5 in `RESIDENT_BACKEND_DESIGN.md`, which had been
left with no default because the answer changed scope. It changes it in more ways than the question
anticipated.

**`docs/design/RESIDENT_BACKEND_DESIGN.md`** — new §3.5, §5.8–5.11, §10, and consequent edits to §6,
§7, §8 and §9. Checklist renumbered §10 → §11.

- **§3.5 — the live stream already crosses roles (`AUDIT`).** `GET /dashboard/events` is guarded by
  `get_active_membership`, not by role, and `RealtimeHub` fans out on `community_id` alone. Any
  active member therefore receives every event in their community, including `0024`'s
  `access_request.created`, which carries an applicant's name and requested relationship. Nothing
  exploits it today because no resident client connects to anything — and the ruling above is
  precisely what stops that being true.
  **This overturns a statement in Session 26's own §8 Q5, which called the stream admin-only.** It is
  not; that mis-stated a live disclosure as a missing feature. Corrected in both documents.
- **§3.5, second half (`DERIVED`).** Twelve tables emit `dashboard.refresh` on every row change and
  the contract for that frame is *re-read your snapshot*. Community-wide delivery to five hundred
  residents means five hundred snapshot fetches per unrelated row change. Audience scoping is a load
  fix as much as a privacy one, which is worth recording because it is the argument that survives
  even if someone decides the disclosure is acceptable.
- **§5.8 (`DERIVED`).** Delivery is three layers and the durable one is not SSE. Every user-visible
  event writes a `notifications` row first; SSE and Web Push are two deliveries of that row. Rejected:
  making the stream the feed — `sse_events` is pruned every fifteen minutes by `0024`, so durability
  built on it is durability built on a table designed to be deleted.
- **§5.9 (`DERIVED`).** `sse_events` gains `audience` / `audience_roles` / `recipient_membership_id`;
  `_Subscriber` gains the membership id and role, both from the verified membership. Rejected: a
  separate resident stream with a topic allow-list — two filters to keep right, and an allow-list is a
  denylist wearing a disguise.
- **§5.10 (`DERIVED`).** One trigger on `notifications` emits the outbox row. Feature code writes
  notifications and never touches the outbox, so live delivery is a property of the system rather than
  a per-feature checklist item.
- **§5.11 (`PO` needed, default set).** Web Push over VAPID, not FCM and not a hosted provider. No
  vendor account, no SDK in a frontend we do not own, and no third party receives who visited which
  flat and when. Stated cost, not buried: on iOS this works only for an installed PWA, and FCM does
  not fix that — a web app on iOS gets web push or nothing.
- **§5.11, amended same session (`PO`).** *"Remember this is a web app."* HomeBandhu ships as a web
  application with no native client planned, so browser capability is the ceiling on every delivery
  mechanism and Web Push is the only available choice rather than the best of several. Recorded
  because it closes the question permanently: when someone rediscovers the iOS limitation, neither a
  native app nor a vendor SDK is the fix, and the constraint should not be relitigated.
- **§10 — the mechanism in full.** Audience table; the `notifications` table the baseline already
  declares and no backend code has ever used; the kind list for both portals; the push sender and the
  single rule that separates it from the realtime hub — *the hub may drop, the sender may not
  duplicate* — resolved with `for update skip locked` in `claim_push_batch`, plus the one-hour claim
  window (a phone that buzzes at 3am about yesterday's visitor is worse than silence) and the
  `404`/`410` → delete rule.
- **§10.5 (`AUDIT`).** The three VAPID settings cannot go in `app/core/config.py` — it belongs to the
  auth workstream and this one does not edit it. They land in a separate settings class instead, with
  the boundary flagged rather than assumed. `pywebpush` is the first backend dependency this
  workstream has added.
- **§10.6 (`AUDIT`).** `frontend/public/` holds a favicon and an icon sprite: no service worker, no
  manifest. Push therefore ships backend-complete and unverifiable end to end until the frontend team
  adds those. Recorded so the test coverage is not later described as more than it is.
- **§6.** Seven endpoints added — `/events`, three notification operations, three push operations —
  taking the proposal from 19 to 26. `/dashboard/events` stays as a deprecated alias: the admin
  frontend is wired to it and this workstream does not break a working client to tidy a path.
- **§7.** Two migrations added, `0028_event_audience.sql` and `0029_notifications.sql`, and they are
  sequenced *before* `0025`–`0027` even though they are numbered after. Every feature RPC calls
  `notify_member(...)`, so the substrate must exist first or each feature gets retrofitted.
- **§9 (`DERIVED`).** Build order re-cut. §3.5 is now step 1, displacing `GET /amenities/available` to
  step 2 — it is the only item that is a defect in shipped code rather than a missing feature, and
  every later step points more clients at the stream it affects.
- **§8.** Q5 answered. Three questions added: whether a push body may carry names and flat numbers on
  a locked screen (default: generic title, detail in-app — a privacy call, so the PO's); per-kind
  preferences (default: all-or-nothing for v1); and who owns the VAPID keypair, which must not be
  committed and which silently unsubscribes every browser if rotated.

**`docs/design/ADMIN_DASHBOARD_DESIGN.md`** — §7 grows a third limit, recording the community-wide
scoping as a property of the design rather than an accident of who happens to be wired up, and
pointing at the fix.

---

## 2026-08-03 — Session 26: writing down why, before building the resident half

Two new documents under `docs/design/`. Both answer the same question — *why is it built this way?*
— which until now was answerable only by reading code and inferring intent. Inferred intent is how a
deliberate constraint gets "cleaned up" by someone who assumed it was an accident.

### `docs/design/ADMIN_DASHBOARD_DESIGN.md` — new — `DERIVED`

Retrospective reasoning for the backend already shipped. Ten sections: the four-layer shape;
authorization (why tenancy is re-read from Postgres on every request rather than trusted from a JWT
claim, and why that cost must not be optimized away); reads-through-views / writes-through-RPCs and
the specific failure each prevents; the additive-migration rule and its corollary that a baseline
mistake cannot be fixed by editing the baseline; wire models as contracts rather than table mirrors;
the error envelope; the SSE outbox; the generated-spec discipline including the union-not-replace and
describe-don't-define rules learned by getting them wrong; a table of what this workstream
deliberately did *not* do; and six rules for extending it.

Nothing here is a new decision. It is the reasoning behind existing ones, recorded before the people
holding it move on.

### `docs/design/RESIDENT_BACKEND_DESIGN.md` — new — `PO` / `AUDIT`

Design for the resident backend, written before the code, marked **proposed**.

**Method — `AUDIT`.** The surface could not be scraped from frontend API calls, because there are
none: all 26 wired call sites in `frontend/src` are auth, registration or admin, and **zero** belong
to the eight resident pages. The requirement was therefore derived from store-slice *behaviour* —
what each action writes and what it refuses to do — which is a better source anyway, being decisions
the product team already made and expressed precisely enough to execute.

**Findings — `AUDIT`.** Four, of which one is a live defect: there is **no amenity list endpoint at
all**. The catalogue reaches a client only inside `GET /dashboard/snapshot`, which requires admin or
manager, and every other amenity read is `_admin`-guarded — while `POST
/amenities/{id}/bookings/request` deliberately carries no admin guard. A resident may therefore call
a booking endpoint with an `amenity_id` they have no legitimate way to obtain: a shipped feature that
cannot be used. It happened because the admin UI already had the snapshot, so nobody ever needed a
list endpoint, and the resident half inherited the absence. Fixing it needs no migration and is first
in the build order.

The others: `complaints` has no column for urgency, location, SLA, rating or reopen count, all of
which the resident form collects; the SLA rule (High 24h / Medium 48h / Low 72h) lives in a frontend
store slice where it is both bypassable and invisible to the admin portal; and `visitor_requests`
already models a scheduled, time-boxed, hashed credential but lacks purpose, guest count and the
short spoken code.

**Rulings — `PO`.** Seven, each with its rejected alternative recorded. The load-bearing ones: the
resident home gets its own `/resident/snapshot` rather than a role-filtered `/dashboard/snapshot`,
because a payload whose shape depends on a runtime role is one `if` away from leaking a
community-wide count into a resident response; the visitor security code is hashed and its plaintext
returned exactly once, accepting that a lost code means reissue, because a code that admits a
stranger through a gate is a credential and `resident_invites` already sets that precedent; and
resident self-payment is a separate endpoint from admin reconciliation, because "record a payment
that already happened" and "initiate one" are different operations that only look alike — with the
explicit constraint that it must never report `succeeded` while no gateway exists.

**Output.** 19 proposed endpoints, three additive migrations (`0025`–`0027`), five open questions
with defaults, a six-step build order, and a ten-point checklist of admin-backend paradigms this
design preserves.

Nothing is implemented. Recorded now so the reasoning is reviewable *before* it is expensive to
change.

---

## 2026-08-03 — Session 25: the same bug, fixed twice, and the merge that settled who owns it

`cfe803c` landed on `main` while Session 24's work was still uncommitted. It fixes **the same defect
Session 24 found** — the spec advertising `HTTPValidationError` for a shape this API never sends —
and fixes it from a better place: `ErrorResponse`, `ErrorBody` and `ErrorDetail` are now pydantic
models in `app/core/exceptions.py`, and `app/main.py` declares `responses={422: ErrorResponse}` on
the router include. The app now states its own error contract instead of a generator asserting it on
the app's behalf.

Two people finding the same defect independently is the system working. Both fixes surviving into
the same file would not be, so this session decides what each side owns.

### `docs/openapi.yaml` — regenerated after the merge — `AUDIT`

`cfe803c` regenerated the spec through the *committed* exporter, which does not know about Session
24's annotation layer. The checked-in file therefore arrived failing three of the four submission
conditions again:

| Condition | On arrival | After regeneration |
|---|---|---|
| Every implemented operation documented | 70 / 70 | unchanged |
| Description per operation | 38 / 70 | **70 / 70** |
| User story mapping | **0** | **70 / 70** |
| Error responses beyond the auto-422 | **1 / 70** | **70 / 70** |

Not a regression anyone introduced — the annotation layer has never been committed, so there was
nothing for their regeneration to preserve. It is an argument for committing it: until it lands, any
teammate running the exporter silently reverts the traceability.

### Schema ownership — the hand-written envelope deleted — `DERIVED`

Session 24's `ERROR_SCHEMAS` defined `ErrorDetail`, `Error` and `ErrorResponse` by hand. Two of
those names now collide with generated models, with a different inner shape (`Error` vs `ErrorBody`).
The hand-written definitions are **deleted**. `api_annotations.py` keeps only `ERROR_SCHEMA_DOCS`,
which contributes descriptions to the generated schemas and only where the generator produced none,
so an upstream `Field(description=...)` always wins.

*Why deletion and not reconciliation:* a schema described in two places is the exact failure this
whole exporter exists to prevent. The code that emits the envelope should define its shape. Prose is
the only thing a pydantic model cannot carry, so prose is the only thing contributed. If the models
are renamed or removed upstream, the enrichment no-ops instead of resurrecting a stale definition.

### Error responses — union, not replacement — `DERIVED`

Session 24's pass **deleted** any 4xx/5xx an operation declared that the annotation table had not
derived. Against `cfe803c` that would have stripped the blanket 422 off 37 operations — silently
narrowing a claim the application had just deliberately made. The rule is now a union: the derived
codes plus whatever the app declares, all rendered through the same `components/responses` entry so
the document reads consistently regardless of origin.

**The cost is stated rather than hidden.** 422 now appears on 69 operations, not the 33 where a
reachable validation error was traced. That over-claims on routes with no body and no typed path
parameter. Over-documenting an error is the cheaper mistake than an exporter overruling a router it
does not own — but narrowing it is the auth workstream's call to make, and is theirs to take.

### `x-no-user-story` — restated as a verdict about what the operation *is* — `PO`

PO ruled that an operation tracing to no story must say `Not covered by user story` and then
classify what sort of API it is. The extension changed from a bare reason string to:

```yaml
x-no-user-story:
  status: Not covered by user story
  api-type: Functional
  rationale: Authentication and session management. Nobody writes a user story about
    signing in until it breaks.
```

Five types, defined in `api_annotations.py`: `Feature`, `Functional`, `Configuration`,
`Master data`, `Non-functional`. Across the 36 untraced operations: Functional 16, **Feature 13**,
Configuration 3, Master data 3, Non-functional 1.

*Why this is worth more than the reason string it replaced:* four of the five types are plumbing,
and plumbing having no story is expected. `Feature` is not. Thirteen operations are user-facing
capability with nothing written about them — which is a gap in the **story set**, not in the API,
and the old free-text reasons buried that distinction in prose. §14.6 now carries the same column.

### `docs/API.md` §1.4, §14.6 — `DERIVED`

§1.4 said the envelope "is now in `openapi.yaml` as `ErrorResponse`" without saying where it comes
from; after `cfe803c` that reads as though this workstream owns a schema it does not. Now records
that the three models live in `app/core/exceptions.py` and that only the prose and the per-operation
code lists come from `api_annotations.py`.

§14.6 gains an **API type** column matching the extension, and a note that the 13 `Feature` rows are
the finding — the other 23 are plumbing behaving as expected.

### Verified

`pytest -q` → 311 passed, including `cfe803c`'s API-016 contract test, which asserts the spec's 422
matches what the runtime emits and passes against the regenerated file. `export_openapi.py --check`
clean, `openapi_spec_validator` OK, `ruff check scripts/` clean, coverage guard clean — the four new
commits added tests, not routes, so the table needed no new rows.

### Not changed, deliberately

No application code, no routers, no tests, no migrations. `cfe803c`'s 422 declaration is left as
written. The two Session 23 dashboard findings remain open — documenting an operation's errors does
not fix a projection that drops fields.

---

## 2026-08-02 — Session 24: the spec is made to carry what the prose already claimed

PO asked whether the four submission conditions — complete API documentation, user story mapping, a
description of each endpoint, and error handling details — were expressible in Swagger, and if so to
make `openapi.yaml` satisfy them. They are: descriptions and `responses` are core OpenAPI, and `x-`
specification extensions are the standard's own mechanism for exactly this kind of traceability. An
audit first, then the work.

### `docs/openapi.yaml` — regenerated, +2,000 lines — `PO`

Four conditions, measured before and after:

| Condition | Before | After |
|---|---|---|
| Every implemented operation documented | 70 / 70 | unchanged |
| Description per operation | 38 / 70 | **70 / 70** |
| User story mapping | **0** occurrences | **70 / 70** carry `x-user-stories` |
| Error responses beyond the auto-422 | **1 / 70** | **70 / 70** |

### `backend/scripts/api_annotations.py` — **new** — `DERIVED`

A table keyed on `(method, path)` supplying the three things FastAPI cannot infer. *Why a table and
not `responses=` on each route:* 33 of the 70 operations live in the other workstream's routers, and
editing those is not ours to do. One table annotates all 70 the same way instead of leaving the
surface half-decorated.

The cost of a side table is drift, so the exporter refuses to build when a key does not match a live
operation, when a live operation has no entry, or when an entry declares neither stories nor a
reason for having none. Adding an endpoint now fails the build until somebody gives it a verdict.
That guard was tested by renaming a key and confirming both halves of the mismatch are reported.

### The error envelope — `AUDIT`

**The one error shape the spec did document was the wrong shape.** 59 operations declared a 422
returning FastAPI's stock `HTTPValidationError` — `{"detail": [...]}` — a response this API has
never sent, because `app/core/exceptions.py` replaces all four default handlers with one
`{"error": {code, message, details}}` envelope. Any client generated from that spec would have
failed to parse every error it received. The correct envelope is now `ErrorResponse`, seven reusable
`components/responses` reference it, and `HTTPValidationError` was **removed** rather than left
beside the truth.

Which codes each operation declares was derived by walking every handler into its services and
repositories and collecting the reachable `raise` sites, then verified by hand. Two corrections came
out of that verification, both recorded in the table: `POST /auth/logout` cannot return 503 (it
catches the provider error and clears the cookies anyway — a logout that fails because Supabase
timed out would be worse than an unrevoked token), and the amenity CRUD routes *can* return 404,
which the first pass missed because those handlers pass their service function to
`run_in_threadpool` as an argument rather than calling it.

### `docs/API.md` §14.6 — count corrected, 33 → 36 — `AUDIT`

**The matrix said 33 of 70 operations serve no story. The right number is 36.** The group table
always summed to 36; the total had been reached by subtracting the endpoints §14.3–§14.5 name, which
assumed every operation not listed as unmapped was mapped. Three were neither — the
`/dashboard/amenities` catalogue writes — and they now have their own row.

Worth recording *how* it was found. The error survived a hand review last session and did not
survive machine-checking the same claim: the coverage guard demands a verdict per operation, and
three operations had none. This is the argument for the guard in one paragraph.

### `docs/API.md` §1.4, §1.5, §14 header, preamble — `DERIVED`

§1.4 now states that the envelope is in the spec and what was there before. §1.5 explains why `400`,
`405` and `429` appear in its table but in no operation — nothing raises `AppError` bare, `405`
comes from the router before any operation is reached, and `429` is not implemented — because
declaring unreachable responses is the same failure in the other direction. The preamble's claim
that the spec covers *shapes* and this file covers *status-code semantics and error codes* was true
and is now false; it has been rewritten to say the spec is authoritative for anything a client must
agree with mechanically, and this file for what a maintainer needs.

### Not changed, deliberately

The four findings from Session 23 stand unfixed: three live in `dashboard_service.py` and
`dashboard_repository.py`, which belong to the dashboard workstream. Documenting an endpoint's error
responses does not fix a projection that drops fields, and the annotation pass was careful not to
paper over it — `PATCH /complaints/{id}` says in its `x-user-stories` role for US-2.8 that assignee
and due date are stored *and dropped before a resident sees them*.

`backend/pyproject.toml` still declares `requires-python = ">=3.10"`, which is false — the code needs
3.11+ for `datetime.UTC`, and a 3.10 virtualenv cannot import the app at all. **Not corrected here**
because `uv.lock` was resolved against `>=3.10` and was regenerated upstream two commits ago;
changing the floor without regenerating the lock with uv 0.11.32 would break teammates' `uv sync`.
Flagged for whoever owns the lockfile.

---

## 2026-07-31 — Session 23: the user stories arrive, and are traced to the API

PO supplied the team's `user-identification.txt` and `user-stories.txt` — the requirements this
backend has been built against for fifteen sessions without ever having them in the repo — and asked
for the endpoints to be mapped to them.

### `docs/product/` — **new**, 3 files — `PO`

`USER_IDENTIFICATION.md` and `USER_STORIES.md` are the team's two documents transcribed verbatim,
plus a `README.md`. Stable ids (`UT-1`…`UT-3`, `US-1.1`…`US-3.6`) were added because a matrix needs
something to point at; no wording was changed and nothing was dropped.

*Why a subfolder rather than two more files in `docs/`:* everything else in `docs/` is a design
artifact we wrote and may revise. These are **inputs**, owned by the team, and the distinction should
survive someone skimming a directory listing. The README says so explicitly, and says to replace
rather than edit them if the team revises the originals.

Two additions that are ours and are marked as such: a table mapping the three user tiers onto the
implemented role model, and a per-story verdict line. The tier table exists because the mapping is
not one-to-one and the mismatch matters — **a staff member has no login**, so every story written in
the voice of a Security Manager is unreachable by that person by construction, not because an
endpoint is missing.

### `docs/API.md` §14 — **new section**, traceability matrix — `PO`

Every one of the 24 stories against the 70 operations, in both directions, with the shortfall named
in each partial row. Coverage: **3 served, 12 partial, 9 none**. §14 pushed the changelog to §15;
the one in-document reference to the range `§7–§14` was updated.

*Why in `API.md` rather than its own file:* PO asked for it in the non-YAML API documentation, and it
belongs there for a better reason than compliance — a matrix kept next to the endpoint prose is
updated by the person changing the endpoint. Kept elsewhere it becomes a snapshot of one afternoon.
The standing rule ("an endpoint added, changed or removed updates the matrix in the same commit") is
recorded at the top of the section for the same reason.

**Four things surfaced that writing the matrix found and reading any single file would not.** — `AUDIT`

1. **Our writes and their reads disagree about four fields.** `PATCH /complaints/{id}` writes
   `assignee`, `due_at` and `progress_percent`; `dashboard_service.py:_complaints()` drops the first
   two and `dashboard_repository.py:66` fetches the third only in its `legacy` branch, so on the path
   that runs against our migrations **every complaint reports progress 0 or 100**. `POST /notices`
   loses `category` and `urgency` the same way (already recorded in §12.1). Each is one line, none is
   ours to change, and together they are not four oversights but one missing convention: nothing
   asserts that a field a write endpoint accepts is a field the snapshot returns.
2. **`complaints` has no priority column** — not in the baseline, not in `0020` — yet
   `dashboard_service.py:86` reads `row["priority"]`, so `urgency` is permanently `Medium`. US-2.5
   asks for a priority selector; it has nowhere to write.
3. **`PATCH /residents/{id}` should come back.** It was removed on 2026-07-30 because no screen
   called it. Correct against the frontend, wrong against US-1.4, which is a direct interviewee
   quote: *"updating resident details such as email addresses is not sufficiently streamlined."*
   The frontend wiring audit is a good test of what the product *does*; it is not a test of what the
   users *asked for*, and this is the first time the two have disagreed.
4. **Four resident stories reduce to one missing decision.** US-2.1, US-2.4, US-2.7 and US-2.3
   downstream all mean *"tell the resident without making them open the app"*. There is no push
   transport of any kind — no device token table, no FCM/APNs registration, no web-push
   subscription — and SSE requires an open browser, which is the precise thing the interviewees said
   they should not need. No amount of further endpoint work closes any of the four.

*One thing the matrix found in our favour, recorded because the rest of this entry is deficits:*
**US-3.1 is most of the way built and nobody planned it.** `visitor_requests` already carries
`pass_hash`, `valid_from` and `valid_until`, and `0018` added
`community_settings.visitor_code_ttl_minutes` — a scheduled, time-boxed, hashed access code, which
is four of the five things that story asks for. The fifth, one code admitting many guests, is the only real schema change.

*Not done, and deliberately:* none of the four findings were fixed. Three live in
`dashboard_service.py` / `dashboard_repository.py`, which belong to the dashboard workstream, and the
fourth is a migration whose column nobody has agreed the name of. §14.7 lists all eight follow-ups
ordered by cost against value; the first five are one-line or one-column changes that close or
half-close five stories.

---

## 2026-07-31 — Session 22: consolidating onto `backend/admin_dashboard`

The whole of `backend/planning/1` was fast-forwarded onto `backend/admin_dashboard`, which sat at
`94556e5` — an ancestor, so no merge commit and no conflicts, and the branch also came up to date
with `origin/main`, which it was 8 commits behind. PO then asked for the stale and irrelevant
material to come out.

### `backend/supabase/migrations/legacy-preauth/` — **deleted**, 9 files — `PO`

The eight pre-baseline migrations and their README. PO's ruling, against the recommendation to keep
them: a branch handed on for review should carry only migrations that will actually be applied, and
the superseded versions stay recoverable in git.

*What that cost, recorded because it is not obvious from the diff:* four of the rebuilt migrations
carried their reasoning by reference rather than repeating it, and `0019` said outright "read that
file for the full derivation of each number on the departments screen". Deleting the folder made
eleven references dangle. Each was repaired rather than dropped — `0019` now gives the `git show`
command that reads the original out of history, and the other four name the file without a path.

The two entries below in Session 20 and Session 18 that point at `legacy-preauth/README.md` are left
as written, per this file's convention; they were true when written.

### `backend/supabase/migrations/README.md` — **new file** — `DERIVED`

Forced by the deletion. The directory now jumps `0008` → `0018`, and a reader with no context cannot
tell whether nine migrations are missing or were never written. It records the gap and why the
numbers are not reused, the mapping from each rebuilt file to what it serves, the `git show` recipe,
and the three tables `dashboard_repository.py` reads in its `legacy=True` branch that are
deliberately never created.

### `FRONTEND_WIRING_AUDIT.md` §5 — repointed — `DERIVED`

The amenities `booking_group_id` reasoning was cited as living in `legacy-preauth/README.md`. It
also lives in the header of `0023_amenities_on_baseline.sql`, which survives, so the citation now
goes there.

### `amenities_repository.py` — stale module docstring — `AUDIT`

Not a `docs/` artifact, recorded here because it was a false claim of the same kind this file exists
to catch. The docstring still said **"None of these database objects exist on the baseline yet"** and
pointed at the quarantine — written before `0023` rebuilt them, and untrue since. It also cited the
pre-baseline `0016` and `0015` for the views and the RPC rationale (now `0023` and `0020`), and
described a booking request as writing "a series, its occurrences, its guests and its charges" — the
two-table model `0023` deliberately abandoned. Corrected on all four points. What replaces it is the
weaker true statement: nothing has been applied to a database yet, and that is true of the whole
admin-dashboard surface rather than amenities specifically.

### `.gitignore` — two entries — `AUDIT`

`graphify-out/` (2.4 MB of code-graph tool output) and `.claude/worktrees/` (agent worktree
checkouts). The latter was excluded only through `.git/info/exclude`, which is per-machine and never
shared, so every teammate was carrying it in their own working tree.

---

## 2026-07-30 — Session 21: live updates for join requests

Pulled `origin/main` @ `ecc8a10` (3 new commits, the unified-auth PR #13). PO asked for a notification on the
admin dashboard when someone requests to join, updating in real time, "lightning fast but minimal in resource
intensiveness", with the mechanism written down.

Investigating it turned up two independent faults rather than one missing feature, which is why this session
touched dashboard files the upstream team owns — **with explicit PO approval, given after the boundary was put
to them.**

### `ARCHITECTURE.md` — new "Live updates" section — `PO`

PO asked directly that the live-update mechanism be documented. Records what we use (SSE over a Postgres
outbox, fanned out by one in-process poller), the cost model, the guarantees, the topic table, and — the part
worth keeping — **why not the alternatives**. Supabase Realtime is the native answer and is deliberately *not*
adopted yet: it is a browser-side WebSocket subscription, so it would mean handing the frontend a Supabase key
and moving tenant filtering into RLS, reversing the "no provider token in the browser" decision the SSE
endpoint exists to enforce. `LISTEN`/`NOTIFY` was rejected for needing a direct Postgres connection the service
does not have. Both are recorded so the next person does not re-litigate them from scratch.

### `API.md` §5.1 — `GET /dashboard/events` documented — `DERIVED`

The endpoint is the dashboard workstream's, but our migrations feed it and it is how every write in §7–§12
reaches an open screen without a matching read endpoint. Documents the `Last-Event-ID` resume contract, the
frame format, all three topics, and the at-most-once guarantee. §5 no longer claims to be "intentionally
empty" — it has content now.

### `FRONTEND_WIRING_AUDIT.md` §7 — the two faults — `AUDIT`

Overturns nothing, but corrects an implicit assumption running through §1: that the SSE outbox meant a write
reached the UI. It did not, for two reasons.

*The notification was never sent.* `AdminLayout.jsx` counts `pendingRequests` and `appStore.js` reads
`snapshot.pendingRequests`. `DashboardSnapshot` had no such field. The frontend was complete and correct; the
key simply never appeared in the payload, so the badge could not render under any conditions.

*The transport could not have scaled.* `event_stream` was a synchronous generator calling `time.sleep(5)`, and
Starlette iterates sync generators in the anyio worker threadpool — so each connected admin pinned one of that
pool's 40 threads for the life of the stream, and the 41st dashboard would starve unrelated requests
process-wide rather than merely lag.

### ERD + class diagram — `DERIVED`

`pending_access_request_overview` added to the view list (no new table — it projects `access_requests`).
`sse_events` note updated for the RLS and retention change. Class diagram gains `RealtimeHub`, `Event` and the
`0024` trigger functions.

**Unrendered.** The `.puml` edit is structurally checked (balanced braces, every referenced identifier
defined) but not rendered — no PlantUML on this machine, and downloading a JAR to execute was not something to
do unasked. Worth a render before submission.

### Security finding: `sse_events` had no RLS — `AUDIT`

Not asked for, found while reading the outbox. The table is reachable through PostgREST and had no policies,
so any authenticated user could read every community's event stream — table names and community ids for
tenants they have no membership in. `0024` enables RLS with no policy, denying everything except
`service_role`, which is the only role the backend uses to read it. Retention is also now bounded; twelve
tables feed that outbox on every row change and nothing had ever deleted from it.

### One frontend file changed — `PO`

Standing rule is that we do not touch `frontend/src`. PO granted an explicit exception for this one case:
`PendingRegistrations.jsx` reads React Query, not the snapshot, so the SSE refresh never reached it and the
badge would have ticked up while the page behind it went stale. Four lines, hung off the
`homebandhu:dashboard-refresh` window event the bootstrap already dispatched. It remains the only frontend
file this branch has touched.

### Documentation audit of the above — four corrections — `AUDIT`

PO asked for a check that the live-update work is fully documented, including `openapi.yaml`, and that nothing
stale or dead was recorded. Four things did not survive it.

**`openapi.yaml` described the stream as JSON.** FastAPI cannot infer a media type from a `StreamingResponse`
return, so it fell back to `application/json` — meaning `GET /dashboard/events` was published as a JSON
endpoint, and a client generated from the spec would have tried to decode a live stream. The route now declares
`text/event-stream` explicitly, plus the `401`/`403` that `API.md` §5.1 already listed and the spec did not.
This is the only code edit of the audit.

**`ARCHITECTURE.md` overstated the outbox.** The parts table read *"Every domain write records that it
happened."* That is false for the seven tables `0018`–`0023` add: none carries a trigger, so a settings or
billing change pushes nothing, and a second admin with that screen open does not see it. Now stated as a
limit, with what closes it (one additive migration extending the `0007` loop) and the note that it is not
scheduled. **This is a real gap in the feature as shipped, not just a wording fix.**

**Retention had no prose anywhere.** `0024`'s comment pointed readers at the *Live updates* section for who
calls `prune_sse_events`; that section never mentioned it. The pointer is now true, and it records the part
that actually matters operationally: the `*/15` schedule exists **only where `pg_cron` is installed**, and on
a project without the extension the outbox grows unbounded.

**Two of our own earlier claims are now false.** `RECONCILIATION_ADDENDUM.md` C-13 — *"their realtime outbox
works on our writes for free"* — was written before we tried to build on it, and both halves of the finding
turned out wrong: `dashboard.refresh` carries too little to notify with, and the reader could not scale. C-13
and the pointer to it in `SCHEMA_RECONCILIATION_PLAN.md` §0 now carry dated amendments rather than being
rewritten, since the reasoning at the time is the part worth keeping. The two trigger gaps C-13 itself named
are recorded as still open.

No dead code found: every symbol added this session is reachable, `read_events` survives as the
community-scoped backfill read (distinct from the global-cursor `read_events_since`), and ruff reports zero
findings across all six files the session touched.

---

## 2026-07-30 — Session 20: rebuilt every quarantined migration onto the baseline

Pulled `origin/main` @ `9f8adc4` (4 new commits) and rebuilt the SQL that had been quarantined since the
baseline replaced the schema it targeted. The trigger was a simple question — is this ready to push? — and the
honest answer was no: 32 of our 35 endpoints had no database objects behind them.

### Merged `origin/main` @ `9f8adc4` — `MERGE`

One conflict, `backend/.venv/pyvenv.cfg`: we untracked it as a build artefact in session 18, they modified it.
Resolved by keeping our deletion — and the merge immediately demonstrated why it mattered, by overwriting the
local venv config with a Linux path and breaking the interpreter. That file has now been clobbered across three
machines (a Mac using uv, a Linux box, this Windows one). It stays untracked.

### Five migrations, `0019`–`0023` — **10 views, 24 RPCs, columns on 11 tables** — `SCHEMA`

| Migration | Replaces | Serves |
|---|---|---|
| `0019_departments_on_baseline.sql` | `0014` | 9 department/staff endpoints |
| `0020_complaint_events_on_baseline.sql` | `0013` | 2 complaint endpoints |
| `0021_money_on_baseline.sql` | `0015` | 4 money endpoints |
| `0022_settings_views_on_baseline.sql` | `0017` views | `GET`/`PUT /settings` |
| `0023_amenities_on_baseline.sql` | `0016` | 16 amenity endpoints |

`0010`–`0012` were deliberately not rebuilt: the reads they backed were removed by the wiring audit.

Three baseline constraints are relaxed rather than removed, each recorded where it happens.
`staff_assignments.membership_id`, `complaint_comments.author_membership_id` and
`amenity_bookings.booked_by_membership_id` all become nullable, because rosters are typed names rather than
accounts and a maintenance block has no resident behind it. `departments.is_active` and `amenities.is_active`
stay truthful, kept equal to our new `status` columns by triggers, because their `dashboard_repository.py:166`
reads them.

### Conflict C-11 — **closed** — `CONFLICT`

The wiring audit deleted our three module endpoints, but `GET /settings` still read modules from tables of ours,
so the duplication survived one level down. `community_module_overview` is now a view over their
`feature_catalog` and `community_features`. `0017`'s module tables are permanently superseded. Three columns
were added to `feature_catalog` instead of a parallel table — `sort_order`, `backend_status`, `backend_note` —
because they describe whether a module a community switched on actually has a backend, which is a fact about our
code rather than about the community. Nothing is seeded as `live`, because nothing is.

### The amenities design question — **settled against our model** — `CONFLICT`

`origin/main` @ `db85c04` rewrote the submission ERD to match the baseline, removing
`amenity_booking_series`, `amenity_booking_occurrences` and the typed `amenity_rules`. The argument in
`legacy-preauth/README.md` — that their own ERD backed our series model — was true when written and is now false.
It has been corrected in place.

Conforming exactly would have cost a product behaviour: a resident books up to 30 dates in one request and an
admin approves the whole request with one click, so one row per date with nothing joining them means approving a
12-date request 12 times. `0023` keeps their single `amenity_bookings` and adds one nullable `booking_group_id`
column. No series entity, no second table, the ERD's table set unchanged, and the name converges with the
`bookingGroupId` their `dashboard_service.py:149` already emits.

### A bug the rebuild exposed — `CORRECTION`

`status_to_storage` mapped `Pending -> 'pending'` and `Reopened -> 'reopened'`. The baseline's
`complaint_status` is an ENUM containing neither, so every `PATCH /complaints/{id}` carrying those would have
failed with `22P02`. The endpoint's tests passed because they never reach a database. Both now store `open`, the
reopen is preserved as a timeline event carrying the previous status, and a new test asserts every mapped value
is a member of the enum. 260 → 268 tests.

### Static validation — `TOOLING`

There is no database, Docker or `psql` on the machine this was written on, so "runnable" could not mean
"applied". Instead `pglast` — the real PostgreSQL parser — checks that every migration parses, that every RPC our
repositories call is created by some migration, and that every column they select exists on the table or view
they select it from.

The column checker was **written, found nothing, and was then proven broken** by injecting a bad column it failed
to detect. Rewritten to walk the AST properly, it found 12 real mismatches: 10 missing columns on
`amenity_overview`, `day_count` on `amenity_booking_overview`, and `invoice_line_items.total_amount`, which
existed but was hidden inside a `DO` block where no static reader could see it. All 12 fixed.

### Submission artifacts — `DOCS`

- **ERD** (`docs/diagrams/homebandhu_submission_erd.dbml`): our 7 new tables added with their relationships, plus
  a comment block listing every column added to a baseline table and every view created. Listed rather than
  edited into upstream's table blocks, so the file stays mergeable.
- **Class diagram** (`docs/diagrams/HomeBandhu-Architecture-Classes.puml`): it modelled only their 6 routers, 6
  services and 6 repositories. Our 7 routers, 7 services and 7 repositories added, with the views/RPC layer and
  the SSE outbox edge.
- **`docs/API.md`**: the 34 sections documenting removed endpoints are gone (2 824 → ~1 770 lines). §5 and §6 are
  now deliberately empty with a note explaining why and where the functionality went; the numbering is kept so
  links into §7–§14 do not break. A mechanical check now reports zero stale headings and zero undocumented
  operations on our side.

### What is still true, and unchanged — `STATUS`

**No migration has been applied to any database, including `0001`.** Nothing here has executed. The claim is that
the SQL is complete, parses, and matches what the code expects — not that it works. That is F1, and it is now the
only thing between these endpoints and working.

## 2026-07-30 — Session 19: cleared the stale residue of the API cut

PO instruction: *"check if there are any stale stuff left from any of our previous and irrelevant stuff from
anything."* — `PO`

Session 18 removed 32 operations from the routers and stopped there. The layers underneath them were left in
place, so the branch carried a large body of code that nothing could reach. This session removed it and corrected
the claims that had gone stale with it.

### Dead code — **855 lines, 50 defs, 18 files** — `AUDIT`

Found by walking the call graph outward from the live routers, then iterating until the set stopped growing (each
pass orphans the helpers the previous pass's deletions were the last caller of). No test referenced any of it, so
none of it was even test-supported.

| Domain | Removed |
|---|---|
| Complaints | `list_complaints`, `get_complaint`, `mark_read`, `register_attachment` and their helpers; 6 of 10 repository functions; 5 of 8 schema classes |
| Money | collection summary, void, maintenance-run paths across service, repository and schemas |
| Settings | the whole module-toggle path (3 service, 3 repository, 2 schema defs) |
| Departments, amenities, people | `list_categories`, `set_amenity_status`, `_tower_of` and their schemas |
| Vocabularies | `status_to_wire`, `urgency_to_wire`, `is_open`, `urgency_to_storage`, `invoice_filter_to_storage`, `unit_label_for` and four status-set constants — the **read**-direction mappings, which went with the reads. `status_to_storage` stays because `PATCH /complaints/{id}` still writes a status. |

Two of these were worse than unused: `complaints_service._unit_codes` queried `apartments` filtered by
`association_id` — both renamed by the baseline — and `settings_repository.set_modules` called an RPC that no
longer exists. Unreachable code cannot fail, but it can be revived by someone who assumes it works.

34 tests were removed alongside, all covering removed features: **294 → 260 passing**. The API surface is
unchanged at 50 paths / 59 operations, which is the point — nothing deleted here was reachable through it.

Also renamed the `dash_repo` alias to `tenancy_repo` in five services: the module it points at stopped being a
dashboard repository when `admin_overview_repository.py` became `tenancy_repository.py`.

### `docs/CLAUDE.md` — **deleted** — `AUDIT`

Deleted upstream at `94556e5` and kept by session 18's merge, which was a mistake: every architectural claim in it
was false by then. It stated *"There is **no backend**"*, described the Zustand store as seeded from
`frontend/src/data/` (deleted in the frontend rewrite) and persisted to localStorage (it is now a render cache
that begins empty), and pointed at `frontend/.oxlintrc.json` and `selfcheck.mjs`, neither of which exists. Their
root `AGENTS.md` covers the same ground correctly. Nothing depended on the file — a `CLAUDE.md` under `docs/` is
not loaded as project context.

### Two claims corrected because they were wrong, not merely stale — `AUDIT`

- **`docs/FRONTEND_WIRING_AUDIT.md` §5** said `0018_settings_on_baseline.sql` rebuilt what `GET`/`PUT /settings`
  need. It does not: 0018 creates the two *tables*, while those endpoints read the `community_settings_overview`
  and `community_module_overview` **views**, which are still quarantined in `0017`. The section now counts
  honestly — **3 of our 35 endpoints would run against a real baseline database**, not the 5 implied.
- **`app/api/v1/routers/settings.py`** claimed `GET /settings` reports modules "read from `community_features`".
  It reads our `community_module_overview`. So conflict C-11's duplication survives on the read side even though
  the module *endpoints* were deleted; the docstring now says so and names repointing that read as the fix.

Smaller corrections in the same pass: `associations` → `communities` in three comments, the `0017_settings.sql`
citation in `settings_schemas.py`, and a quarantine note added to the four repository docstrings whose views and
RPCs do not exist on the baseline — a reader following "the three views from migration 0015" would otherwise go
looking in `supabase/migrations/` and find nothing.

---

## 2026-07-30 — Session 18: merged, and cut the API down to what the frontend calls

PO instruction: merge their work in via git so the folder never has to be shared again, wire our backend to what
the frontend and their backend actually provide, **edit or remove every endpoint of ours with no frontend call**,
do not edit their work, and leave the branch so merging it to `main` produces no conflicts. — `PO`

Merged `origin/main` @ `94556e5` into `backend/planning/1`. Three conflicts, all resolved: `.gitignore` (union),
`backend/app/api/v1/__init__.py` (their list plus one line for our router), `docs/CLAUDE.md` (kept ours; they
deleted it). Verified with `git merge-tree` that merging this branch into `main` now reports **zero** conflicts.

### `docs/FRONTEND_WIRING_AUDIT.md` — **new file**

- **The organising rule that settled every endpoint:** *their snapshot is the read path; ours is the write path
  plus the reads the snapshot cannot serve.* Recorded because it is only coherent thanks to the SSE outbox
  (addendum C-13) — our writes fire triggers that make the frontend re-snapshot, so a write needs no matching
  read of ours. Without that fact the removals would look like losing functionality. — `DERIVED`
- **32 operations removed, 87 → 59** (ours: 35). Includes our whole dashboard-overview router, which resolves
  conflict **C-2** by deletion rather than by keeping two dashboard APIs, and the six amenity CRUD endpoints their
  `/dashboard/amenities` already serves. Per-endpoint reasoning is tabulated in the doc so each removal can be
  argued with individually. — `PO`/`AUDIT`
- **Two endpoints added**, both dead frontend interactions with no endpoint anywhere: `POST /notices`
  (`addNotice`) and `POST /admins` (`addAdmin`). — `AUDIT`
- **`POST /admins` promotes an existing member rather than inviting one.** Their invitation flow hardcodes
  `intended_role = 'resident'` (`invitations_repository.py:40`) and `CreateInvitationRequest` has no role field, so
  an admin-bound invite cannot be minted without duplicating token machinery this workstream does not own.
  Promotion is also the flow `roles.md` describes. It 404s for a non-member, which is a frontend-facing
  consequence and is on the agenda. — `DERIVED`
- **Corrected mid-audit:** `GET /complaint-categories` was first justified as "the page derives its filter list
  from complaints it has". The real reason is that `CreateDepartment.jsx` collects categories as **free text**, so
  no vocabulary is ever fetched. Same outcome, but the wrong reason would have made re-adding it look safe. — `AUDIT`
- **Two survivals recorded as judgement calls, not callers.** `POST /invoices` and `POST /invoices/{id}/payments`
  have no UI caller; they are kept because `PUT /billing-settings` is called and billing settings over a system
  that cannot issue or settle an invoice configure nothing. Logged explicitly so the deviation from the PO's rule
  is visible rather than silent. — `DERIVED`
- **`payInvoice` must not be wired to the payment endpoint.** It settles an invoice, so exposing it to the payer
  lets a resident clear their own dues by assertion. Resident self-service needs a gateway webhook. — `AUDIT`
- **§6 lists two one-line changes the dashboard workstream should make** (department staff stub; notices dropping
  `category`/`urgency`). Written as a request rather than made as an edit, because both files are theirs. — `AUDIT`

### `backend/supabase/migrations/legacy-preauth/README.md` — **new file**

- **Migrations `0010`–`0017` quarantined.** 7 315 lines with **256 references to tables the baseline deleted**.
  Kept rather than deleted because the reasoning in the comments is the expensive part and the rebuild is a
  translation, not a redesign. Moved rather than left in place because two mutually exclusive sets of unapplied SQL
  in one directory — the baseline needing a fresh project, `0010`–`0017` assuming `0001`–`0003` — made applying the
  wrong set a way to lose a database. The README carries the full rename map and the rebuild order. — `AUDIT`
- **The amenities design question is left open on purpose**, with the cheapest additive path recorded: add
  `amenity_booking_series` plus a nullable `amenity_bookings.booking_series_id`, treating their rows as our
  occurrences. Noted that their `dashboard_service.py` already reads `booking_series_id` in its legacy branch, and
  that their own ERD models series + occurrences — so on amenities their artifacts side with our design. — `DERIVED`

### `docs/openapi.yaml`

- Regenerated: **50 paths, 59 operations**. Generated, never hand-edited, per the API docs standard. — `DERIVED`

---

## 2026-07-30 — Session 17: the rest of the handover — they rewrote the frontend

PO instruction: *"did you look at all the others in the folder I shared above or just the backend? compare all
the files in it?"* — Session 16 reviewed `backend/` and the ERD only. This session compared the whole tree and
produced an addendum rather than editing the plan, so the plan stays readable as the SQL/repository document. — `PO`

### `docs/RECONCILIATION_ADDENDUM.md` — **new file**

- **`3116027..94556e5` changes 166 files outside `backend/`: 93 in `frontend/` alone, 5 907 deletions.** The
  session-16 plan missed all of it. — `AUDIT`
- **The frontend is no longer a dummy-data demo.** Every fixture in `frontend/src/data/` is deleted; `appStore.js`
  is now a render cache whose collections *"begin empty"*; the whole dashboard hydrates from
  `GET /dashboard/snapshot` and refreshes on SSE `dashboard.refresh`. Recorded because it retires the standing
  assumption that frontend data shapes are throwaway — a real serializer must now produce them, so they are
  contractual. — `AUDIT`
- **C-8: none of our 70 operations has a frontend caller.** The client calls 19 paths, and amenity mutations go to
  `/dashboard/amenities`, not our `/amenities`. Logged as the honest status — our API surface is now a *proposal*,
  not the implementation of an existing contract — because it is the one finding that changes what nine build
  steps are worth, and it is a joint-meeting decision, not a code change. — `AUDIT`
- **C-9: `require_csrf` appears zero times in all nine of our routers**, while their client sends `X-CSRF-Token` on
  every unsafe method. Under cookie auth that makes our 47 writes a CSRF hole. Fix is nine router-level lines in
  Phase 1. Consuming their primitive, not editing it, so it stays inside the "leave auth to its owner" boundary. — `AUDIT`
- **C-10: `docs/frontend-documentation.md` (3 305 lines) is deleted upstream** — that is gate 1 of the five-gate
  check. Also `docs/AGENTS.md`, `docs/CLAUDE.md`, `docs/plan.md`. Gate 1's source is to be repointed at
  `docs/FRONTEND_CHANGES.md` + live `frontend/src/`, so the gate keeps meaning instead of citing a deleted file. — `DERIVED`
- **C-11: step 9's `module_catalogue` duplicates their `feature_catalog`, with byte-identical ten keys and
  defaults** — both derived from `onboardingModules.js`. Resolution is to fold our `sort_order`/`backend_status`/
  `backend_note` into their table. Cheapest fix in the reconciliation, and it keeps all of step 9's documentation. — `AUDIT`
- **C-13 corrects a session-16 worry in our favour.** I expected to add outbox emission to 47 writes. The outbox is
  `AFTER INSERT/UPDATE/DELETE … FOR EACH ROW` triggers over twelve tables, so **our writes refresh the UI for free,
  including writes inside our RPCs**. All twelve tables verified to carry `community_id`. Phase 5 shrinks. — `AUDIT`
- **C-14: their baseline closes F2, F3 and F4** — `media`, `rate_limit_buckets`, `idempotency_records`, and
  `aggregate_version` on `complaints`/`amenity_bookings`. Schema only, no Python reads them, but three open
  questions become implementation tasks. — `AUDIT`
- **C-15: our error envelope already matches their client exactly** (`{error:{code,message,details}}`), verified
  against `client.js`. Independent convergence; no change needed. — `AUDIT`
- **C-16 sharpens the amenity argument.** Set-comparing their ERD against their baseline: 20 ERD tables absent from
  the baseline, 15 baseline tables absent from the ERD. The ERD models `amenity_booking_series`,
  `amenity_booking_occurrences` and a typed `amenity_rules` — **our step-8 design, not their `booking_rules jsonb`**.
  Their baseline deviates from their own submitted ERD, which is a stronger case for our typed design than our
  own preference is. — `AUDIT`

### `docs/SCHEMA_RECONCILIATION_PLAN.md`

- Pointer added to the addendum at the head of the file. The plan's phases are amended by addendum §3 rather than
  edited in place, so the approved document is not silently changed under the PO. — `DERIVED`

---

## 2026-07-30 — Session 16: the auth team's `origin/main` turns out to contain the whole domain

PO instruction: a copy of `origin/main` was handed over as *"the changes made by the backend team with
regard to login and authentication"*, with the ask to refactor our work onto it, find the conflicts, and
**produce a plan before implementing anything**. No code or migration has been changed yet. — `PO`

### `docs/SCHEMA_RECONCILIATION_PLAN.md` — **new file, then rewritten the same session**

- **The handed-over folder was one commit stale, and the missing commit invalidated the first draft.**
  `origin/main` is at `94556e5`, which **deletes migrations `0001`–`0005` and replaces them with a single
  263-line `0001_baseline.sql`** headed *"apply only to a new Supabase project"* — reshaping and renaming
  the tables **again**. Their schema has now been rewritten twice in two days. The plan was rewritten
  against `94556e5` alone, and the churn itself became an argument in it: a translation layer we own
  (our views) is the right place for that risk to sit. — `AUDIT`
- **The deepest conflict is not tables, it is where authorization lives.** Their baseline enables RLS on
  **6 of 46 tables** with 7 SELECT policies, and guards everything else in Python over a service-role
  client. Our build plan commits to *"RLS as the enforcement boundary"*, and our `get_request_client()`
  reaches those tables with a **user** token — where no policy exists. Recommended fix is additive (RLS
  for the ~14 tables we read), because it asks them to change nothing and returns the cross-tenant
  guarantee to the database. **This gates every repository change**, so it is decision 1. — `AUDIT`
- **There are now two dashboard APIs, in three files with identical paths** — they wrote
  `dashboard.py`, `dashboard_service.py` and `dashboard_repository.py` too, so git will report
  *both-added* conflicts. Judged complementary rather than duplicated (their one-shot snapshot + SSE for
  the home screen; our resource endpoints for anything that pages, filters or writes), so the
  recommendation is to rename ours and keep both. — `AUDIT`
- **Their auth seam is friendlier than their own notes suggest**: `_extract_token` accepts a bearer
  header *or* the new session cookie, so our documented contract and all seven routers' identity
  dependencies keep working. What does break is `require_role`, now `require_membership_role` over a
  membership row rather than a JWT claim — and adopting it lets us **delete** `get_caller_community_id()`
  rather than repair it, removing our worst single point of failure. — `AUDIT`
- **Their ERD documents a schema that no longer exists** — the `.dbml` still describes the deleted
  `0004` tables. Flagged for them. — `AUDIT`
- **F1 got worse, and this is the one to act on soonest.** There are now two mutually exclusive sets of
  unrun SQL — their baseline demands a fresh project, our `0010`–`0017` assume `0001`–`0003` — so
  **applying the wrong set first is now a way to lose a database.** — `DERIVED`

- **The premise of the handover is wrong, and that is the finding.** Commit `0fffb68` is not an auth
  change: it ships **1,831 lines of SQL implementing the entire application domain** — 48 tables, RLS on
  all of them, three workflow RPCs — plus a new 868-line ERD that matches it. **Sixteen of those tables
  are tables we also built, under the same names, with different columns.** So the task is reconciling
  two independent implementations of one domain, not adapting to a new login flow. Recorded first,
  because it changes what "refactor" means. — `AUDIT`
- **Seven of our open items are closed by their work**, and the plan says so before it lists a single
  conflict: §1.1 (privilege escalation — `handle_new_user()` no longer reads the role from signup
  metadata), §1.2 (closed **differently** — `is_admin()` is still global but is now used by *zero*
  policies; all 50 read policies use new per-community helpers), C1 (email, as `display_email`), C2
  (they took exactly `0004`–`0005`), C3 (they reached our set-returning conclusion independently), C6/F5
  (`.venv` untracked), D1 (the rename we deferred has happened). — `AUDIT`
- **Their JWT contract is compatible with ours** — the access-token hook emits `user_role` uppercase,
  which is what our `deps.py` already parses. The auth seam needs no change, which is the one thing the
  handover *was* about. — `AUDIT`
- **The blast radius is SQL, not Python.** Our API layer reaches the database through our own views and
  RPCs; across `app/` there are only **11** references to any renamed table. Rewriting 12 views is what
  buys back most of 70 endpoints — this is the fact the whole plan is built on. — `DERIVED`
- **One function is the linchpin.** `get_caller_community_id()` reads `profiles.association_id`, which
  their `0004` renames to `legacy_community_id` and stops maintaining. **Every one of our 70 operations
  calls it**, and it is a one-function fix. — `AUDIT`
- **Their exclusion constraint reproduces the bug we filed as A18.** `amenity_booking_occurrences` has a
  **blanket** overlap exclusion while `amenities` carries `capacity` and `booking_mode` — so capacity is
  unreachable, exactly the frontend bug (A18/E17) now in the database. Logged as a push-back with a patch
  rather than something to work around: **their tables now, so their fix.** — `AUDIT`
- **Their RLS grants no admin write anywhere** — 50 SELECT policies, 3 resident INSERTs, 1 UPDATE. Our 32
  RPC writes fit that model; our **9 direct PostgREST writes do not** and must become RPCs. — `AUDIT`
- **Recommendation recorded with its reasoning, not just its conclusion:** their schema becomes the base
  and ours becomes additive `0018`+, because theirs is merged and ours is not, because neither has been
  applied so both are equally unproven, and because what we actually contributed — the API layer, the
  vocabulary translation, billing settings, the SLA taxonomy, amenity settings, module metadata — all
  survives the move. **Three push-backs are named** where adopting theirs would be wrong. — `DERIVED`
- **Their ERD and their migration disagree**: the `.dbml` has 48 tables and omits `feature_catalog` and
  `community_features`, which `0004` creates and `0005` writes policies for. Flagged for them rather than
  absorbed. — `AUDIT`
- **Two questions are held open rather than assumed**: whether the recommended direction is accepted, and
  whether our work may be committed before merging 1,831 lines of someone else's SQL into an uncommitted
  tree — the one step in the plan that could lose work irrecoverably. — `PO`

---

## 2026-07-30 — Session 15: build step 9 (settings — community preferences and feature modules)

PO instruction: **proceed with step 9**, then, partway through: *"break it down into smaller sub steps
that you can do one at a time."* The build plan's line for this step is one sentence — *"Only
`community_modules` and real community settings. Billing and late fines are not settings."* — and the
work under it turned out to be the widest of any step relative to that sentence. **Working order is now
the PO's to set**, and the documentation pass was done as five separately-reported sub-steps rather
than one. — `PO`

### The finding that made this step different from every other one — `AUDIT`

**The admin Settings screen has never saved anything.** `pages/AdminDashboard/Settings.jsx` is 135
lines: four `useState` toggles and

```js
const handleSave = () => { showToast('Admin Settings Saved Successfully', 'success'); };
```

No store slice, no service module, no persistence. An admin flips four switches, is told they saved,
and loses all four on reload. It is the only screen in the product whose save button is a lie.

**The consequence for this step is structural, not cosmetic**: every other section of `API.md`
reproduces a shape the frontend already has, and here there was nothing to match, so **the field names
are ours**. That is worth the frontend team's attention *now*, while nothing depends on them — raised
as `DECISIONS_NEEDED.md` B17 and agenda item 17.

### The second finding: the four toggles are four different kinds of thing — `AUDIT`

One card, four switches, and no two of them belong to the same subsystem:

| Screen label | What it actually is | Where it landed |
|---|---|---|
| Automated Monthly Maintenance | billing | `community_billing_settings.auto_billing_enabled` |
| Late Payment Fine Charges | billing, for a feature that does not exist | `community_billing_settings.late_fee_enabled` |
| Gate Security App Pre-approvals | a visitor policy, with no visitor backend | `community_settings.require_visitor_preapproval` |
| Urgent Notice SMS Broadcast | a notification policy, with no SMS provider | `community_settings.notice_sms_broadcast_enabled` |

**One table would have been the mistake.** The first two are money and money already had a home from
`0015` — which is what the build plan's "billing and late fines are not settings" means in practice.
The last two describe features that exist only as frontend dummy data. All four are readable in one
`GET /settings` because the screen draws them together; **the billing pair is read-only there**, since
two writers is how one rate starts disagreeing with itself. — `DERIVED`

**Three of the four are stored and read by nothing, and `API.md` §11 says so out loud** rather than
leaving it to be discovered: nothing runs billing on a schedule, nothing charges a late fee, and there
is no visitor table or SMS provider in the repository. Storing them is still the point — the screen
currently *loses* them. Raised as A22 (🔴) and A23 (🟡).

### `0017_settings.sql` — **new migration**, two tables, two views, five functions

- **The ERD's `enabled_modules jsonb` became a table.** A jsonb array cannot record **when** a module
  was switched off or **by whom**, and that is the first question anyone asks after it happens.
  `community_modules` (from `0011`) already carried both columns; `0017` adds `module_catalogue` beside
  it, because the ERD names a home for the module *selection* and none for the module *definitions*.
  — `AUDIT`
- **The catalogue drives both views, not `community_modules`.** `cross join` the catalogue, `left join`
  the community's rows: a community missing a row for a key reads as that key's default with
  `isDefault: true` rather than the key vanishing from the list. An eleventh module added later appears
  everywhere immediately. — `DERIVED`
- **Module enforcement was deliberately not implemented**, and the two reasons are only visible from
  the seed data. `amenities-booking` ships **disabled** (`onboardingModules.js` has
  `defaultEnabled: false`, and `0011` seeded it that way), so enforcing the rule would `403` **all
  twenty-two step-8 endpoints on every community that exists** — a data-driven outage rather than a
  feature. And six of the ten modules have no backend to gate, so the rule would be real for four keys
  and decorative for six. **What replaced it is `module_catalogue.backend_status`**
  (`implemented` / `partial` / `none`) plus a per-module note, so the state is reported honestly rather
  than enforced wrongly. A24 (🔴). — `AUDIT`
- **Nothing in the frontend gates on a module either.** `AdminLayout.jsx:34-43` is a fixed ten-item nav
  array, and no route, screen or store reads `enabledModules` — so enabling or disabling a module
  currently changes nothing anywhere, on either side. — `AUDIT`
- **`community_settings` holds only what had no home**: `timezone`, `unit_label_singular`,
  `invite_ttl_hours`, `visitor_code_ttl_minutes`, the two policy toggles, and `version`. The ERD also
  puts `default_currency_code` and `invoice_number_prefix` here; `0015` had already put them in
  `community_billing_settings`. Recorded with the rest as D8. — `DERIVED`
- **This step answers A10, and it vindicates `0016` rather than reversing it.** `timezone` now exists
  and is a real IANA name. A booking made for 07:00 must still read 07:00 after somebody *corrects* a
  wrong timezone, which is only true because `0016` stores wall-clock `date` + `time`. What the
  timezone unlocks is anything needing an absolute instant. — `DERIVED`
- **The timezone is validated in the RPC against `pg_timezone_names`, not by a `CHECK`.** A `CHECK` must
  be immutable and the timezone catalogue is loaded from the host and changes between Postgres
  releases. The catalogue's spelling is what gets stored, so `asia/kolkata` saves as `Asia/Kolkata`.
  — `DERIVED`
- **Two cross-field `CHECK`s give the billing toggles teeth**: `auto_billing_enabled` cannot be true
  while `default_maintenance_amount` is null, and `late_fee_enabled` cannot be true without
  `late_fee_amount > 0`. A `BEFORE` trigger raises `HB409` with a message naming the field; the
  `CHECK`s remain as backstops against direct SQL. **A patch that silently ignored the key would be
  worse than one that fails** — the API would return `200` and the toggle would spring back on the next
  read, which is the exact bug the current frontend has. — `DERIVED`
- **`late_fee_amount` is nullable and null means "not configured".** The screen's prose mentions ₹100;
  adopting it as a default would repeat exactly the A13 mistake — a number nobody chose, indistinguishable
  from one they did. — `AUDIT`
- **`unit_label_singular` is nullable and null means "derive it"** — `Flat` for `apartment`, `Villa`
  otherwise — because a stored default goes stale the day a community changes type. The rule
  necessarily exists twice, in SQL and in Python (`vocabularies.unit_label_for`), so the two are tested
  against each other. — `DERIVED`
- **`update_billing_settings` was replaced in full rather than extended alongside**, keeping the same
  signature so `0015`'s grants survive, with six new key-presence branches. — `DERIVED`
- **`module_catalogue` has a read policy and no write policy at all.** It is seed data; it changes by
  migration. — `DERIVED`
- **No endpoint writes `associations`, so an admin cannot rename their community.** It is the one table
  this build plan touches whose admin write policy carries no community clause (build plan §1.2, owned
  by the auth workstream), and a rename would be the first of seventy operations to depend on it. A real
  gap in the settings screen, left deliberately. C7 (🔴). — `AUDIT`
- **One verification query in the footer can legitimately return rows** — stale `community_modules`
  keys with no catalogue entry, since `0011` seeded keys before the catalogue existed and no FK was
  added on purpose. Noted in the file so whoever runs it does not read a real result as a failure.
  — `DERIVED`

### `API.md` — new §11, two sections renumbered

- **§11 Settings** documents five endpoints with full status-code tables, the four-toggle table, the
  ten-module catalogue table, and an explicit subsection on **the two things this step declined to
  build**. §11/§12 became §12/§13. — `PO` standing rule
- **`GET`/`PUT /billing-settings` extended** with the six new fields, the two `409` cross-field rules,
  and corrected `422` bounds. — `DERIVED`
- **`GET /settings/modules` is readable by any authenticated role**, unlike the rest of the section: if
  module state ever gates navigation then every shell needs it, and a resident learning the marketplace
  is off discloses nothing. — `DERIVED`
- **§12 "Not yet implemented" no longer lists any endpoints.** The build order is exhausted, so it now
  points at what actually remains — the unapplied migrations, the Storage bucket, rate limiting,
  concurrency — plus the two frontend surfaces with no backend at all (visitors, and writing notices).
  — `DERIVED`

### `openapi.yaml`

- Regenerated: **70 operations across 55 paths**, up from 65/52. Test count 237 → **275**, including a
  test pinning the Python unit-label rule against the SQL one and another pinning the module counts the
  snapshot computes in SQL against the ones the module list computes in Python — the same screen showing
  two different counts is worse than showing neither. — `PO` standing rule

### `DECISIONS_NEEDED.md`

- **A10 answered** — the timezone is real, and the answer is written up as vindicating `0016` rather
  than reversing it. First item in this file to be closed by a later step.
- **A22** 🔴 automatic billing and late fines are labels for machinery that does not exist
- **A23** 🟡 two toggles stored and read by nothing, with the reasoning for their defaults
- **A24** 🔴 should turning a module off actually switch the feature off?
- **B17** 🔴 the Settings screen saves nothing, so its field names are ours
- **C7** 🔴 §1.2 is now the only thing between an admin and renaming their community
- **C8** 🟡 `invite_ttl_hours` is stored; `invitation_service.py` still reads the env var
- **D8** 🟡 four `community_settings` deviations, **and the ERD's "nine feature modules" should read
  ten** — ten in `onboardingModules.js`, ten seeded by `0011`, ten in the catalogue
- **E21–E24** added; **E1** refreshed to `0010`–`0017` / 275 tests; **E19** notes that step 9 made the
  UTC-completion problem fixable and did not fix it; **B7** raised 🟢 → 🔴 now that the endpoints it was
  waiting for exist; **F1** widened to eight migrations; **F4** notes that `version` increments on every
  write and nothing checks it, making `PUT /settings` the cheapest place to prove the pattern. — `AUDIT`

### `FRONTEND_MEETING_AGENDA.md`

- **Item 17** — the Settings screen persists nothing, and the onboarding wizard's promise that
  *"These features can be changed later from the Admin Settings page"* (`FeatureConfigurationPage.jsx:79`)
  is kept by no screen. — `AUDIT`

---

## 2026-07-30 — Session 14: build step 8 (amenities — catalogue, bookings, ledger)

PO instruction: **proceed with step 8.** No new standing rules; the five-gate check, the change log,
`API.md` and `openapi.yaml` all applied as usual.

### The finding that has no workaround — `AUDIT`

**The frontend has two unrelated amenity products.** `features/amenities/` is a 114-file subsystem
with a catalogue, a four-tab per-amenity workspace, multi-day resident bookings and a financial
ledger. `data/amenities.js` + `store/slices/createAmenitiesSlice.js` is a second one: ids `a1`–`a4`, a
`timing` display string, a status vocabulary of `Available` | `Bookable` | `Open` |
`Under Maintenance`, and bookings whose time is the string `'07:00 AM - 08:30 AM'`. Nothing links
them. The resident Amenities screen reads the first; ResidentLandingPage reads the second, and both
are live.

**No backend can serve both shapes at once**, which makes this the first item on the frontend agenda
where "we already absorbed it" is not available. We built the first, because it is the one the admin
dashboard uses and the one the ERD describes. Raised as `DECISIONS_NEEDED.md` A17 and agenda item 14.

### The live bug that changes our behaviour — `AUDIT`

**The cleaning buffer makes shared capacity unreachable.** `validateBookingSlot` rejects any booking
overlapping a buffer block **in every mode**. On the seeded gym — `Shared`, capacity 24, buffer 15
minutes — an existing 07:00–09:00 booking produces a buffer at 09:00–09:15, so a second resident
asking for 07:30–09:30 is refused, and so is every other overlapping request. A shared amenity with a
non-zero buffer accepts exactly one booking at a time and its capacity of 24 can never be reached.
The seed data hides it: no two gym bookings overlap.

Here the buffer applies only between uses that occupy the amenity **exclusively**. **This means the
API accepts bookings the demo refuses**, which is a deliberate behavioural difference and is written
up as A18 (🔴, with an answer box) and agenda item 15 rather than buried.

### `0016_amenities.sql` — **new migration**, seven tables

- **Overlap is guarded twice, because neither guard alone is enough.** The ERD's note says to use a
  time-range exclusion constraint; **that is only correct for exclusive amenities** — a blanket one
  would make every shared amenity single-occupancy and `capacity` a number nothing reads. So: an
  `EXCLUDE USING gist` constraint scoped `where is_exclusive` for the strict case, **plus** a `BEFORE`
  trigger for what an `EXCLUDE` predicate cannot express. A predicate is per-row: it cannot say
  "conflict if *either* side is exclusive", and it cannot count against capacity. — `DERIVED`
- **The trigger takes `pg_advisory_xact_lock` on the amenity before it looks**, so it is a real
  constraint rather than the check-then-act race a service-layer check would be. Two residents
  booking the last place serialise; the second loses. — `DERIVED`
- **The trigger recomputes the time ranges rather than reading `NEW.slot`.** PostgreSQL fills
  generated columns *after* before-triggers run, so both would be NULL and every `&&` would return
  NULL — a guard that passes everything while looking like it checks. Found while writing it. — `AUDIT`
- **Approval belongs to the series, not the day.** `createResidentAmenityBookingSeries` creates N
  records and `approveAmenityBookingRequest` approves one, so a three-day request can be approved on
  Monday and rejected on Tuesday. The ERD's series/occurrence split puts the decision where it
  belongs. `GET /approvals` returns one row per request with `dayCount` and `dates`. — `DERIVED`
- **Occurrences carry no personal data on purpose.** RLS cannot hide a column, and a resident must be
  able to see that 15:00–17:00 is taken without seeing who took it — so the privacy boundary had to
  be a table boundary. Residents read every occurrence in their community and only their own series.
  — `DERIVED`
- **Four stored values became derived**: `pendingRequests` and `outstandingDues` on the card (the mock
  stores 5 against 1 real request, and 4800 against 1600 in charges), `paymentStatus` on the ledger
  row, and the `completed` booking status — which means "approved and in the past", a fact about the
  clock. Same argument that kept `overdue` out of `0015`. — `AUDIT`
- **Nothing stores a balance.** Charges say what is owed; `amenity_financial_events` says what moved.
  There is no balance to drift, which is `0015`'s rule reached by having nothing to recompute. — `DERIVED`
- **A refund's amount is computed in Postgres and is not a request parameter.** A refund whose amount
  the caller chooses is a refund somebody can ask to be larger. The frontend already sends none. — `DERIVED`
- **`assert_billing_admin` was redefined to delegate to a new `assert_community_admin`** rather than
  copy-pasted under a second name — the exact mistake `0015`'s own comment warns about. — `AUDIT`
- **`invoice_line_items.amenity_booking_charge_id` added**, the column `0015` deferred on the grounds
  that a nullable pointer to a table that does not exist is a pointer nothing checks. — `DERIVED`
- **Five deliberate ERD deviations**, all recorded as D7: `amenity_settings` replaces the versioned,
  weekday-scoped `amenity_rules` (which covers 8 of ~30 settings fields and has no screen writing
  either of its axes); local `date` + `time` rather than `timestamptz`, because there is no community
  timezone field anywhere to resolve "07:00" against; `booking_guests` renamed for prefix consistency;
  `location` and `image_url` added; `blocked` and `pending` added to occurrence status. — `DERIVED`

### `API.md` — new §10, two sections renumbered

- **§10 Amenities** documents twenty-two endpoints with full status-code tables. §10/§11 became
  §11/§12. — `PO` standing rule
- **`POST /amenities/{id}/bookings/request` is not admin-only.** It is here in an admin-scoped build
  because the approvals tab is otherwise a screen that can never have anything on it — the same
  argument step 7 made for the invoice write endpoints. — `DERIVED`
- **`GET /amenity-reports` splits rows from KPIs.** `rows` is a page; `kpis` is an RPC aggregate over
  every matching row. `calculateAmenityReports` computes all six in the browser, one of them labelled
  **Total Revenue** — the same failure as the money tiles. — `AUDIT`

### `openapi.yaml`

- Regenerated: **65 operations across 52 paths**, up from 43/34. `tests/test_openapi_spec.py` gained
  two more mounted-router assertions. Test count 161 → **237**. — `PO` standing rule

### `DECISIONS_NEEDED.md`

- **A17** 🔴 two unrelated amenity products — which one is real?
- **A18** 🔴 the cleaning buffer made shared capacity unreachable; confirm the fix
- **A19** 🟡 one click now approves a whole multi-day request
- **A20** 🟡 an amenity with bookings cannot be deleted, only deactivated
- **A21** 🟢 deposits are money held, tracked separately from invoices
- **B14–B16**, **D7**, **E16–E20** added; **E1** refreshed to `0010`–`0016` / 237 tests and widened
  (this is the first migration resting on things only Postgres can do); **F1** sharpened; **F4**
  re-dated to "before step 9" with six last-write-wins surfaces. — `AUDIT`

### `FRONTEND_MEETING_AGENDA.md`

- **Item 14** — two unrelated amenity products. The one item on the list where "we absorbed it" is
  not available.
- **Item 15** — the cleaning buffer bug, and the behavioural difference it forced.
- **Item 16** — the approvals row cannot say how many days it is approving. — `AUDIT`

---

## 2026-07-29 — Session 13: build step 7 (money — invoices and payments)

PO instruction: **proceed with step 7.** No new standing rules; the five-gate check, the change log,
`API.md` and `openapi.yaml` all applied as usual.

### The finding that shaped the whole step — `AUDIT`

**There is no maintenance amount anywhere in this product.** Not in the frontend, not in the ERD, not
in any settings screen. It exists as the literal `4250` inside `createPendingRequestsSlice.js`'s
approval handler, repeated in `data/payments.js`. The first thing a real backend needs in order to
bill anybody was missing, and the demo hides it because the invoice array is seeded.

Consequence: `community_billing_settings` is a **new table with no counterpart in the ERD**, holding
the rate, the due day, the currency, the tax percent and the invoice-number counter. It is
deliberately **not** named `community_settings` — `0011` already chose a `community_modules` *table*
over the ERD's `community_settings.enabled_modules` jsonb, so that name is already not the shape the
ERD describes, and claiming it here would collide with step 9. Raised as `DECISIONS_NEEDED.md` A13.

### A build-plan line that was overtaken by an earlier ruling — `DERIVED`

`0012_people.sql` recorded that the invoice half of *"approve creates residency AND first invoice in
one transaction"* would slot into `approve_registration_request()` in step 7. **It does not, and the
premise is what changed.**

The frontend seeds an invoice inside `acceptRequest()` because there, approval creates an *active
resident*. Ours does not — the standing ruling is that the invite token is a mandatory second factor,
so approval mints an invitation and nothing else. **Nobody has moved in at that moment.** Seeding an
invoice there would put a receivable against a flat that may never be occupied, and it would land in
the admin's "Outstanding Receivables" tile as money nobody owes.

The equivalent moment is redemption — which today creates a profile but no residency at all, a gap in
the auth workstream's half. So billing is explicit instead: `run_maintenance_billing()` bills every
**occupied** unit for a period, on the same cycle as every other flat rather than on the anniversary
of one approval. Recorded in the `0015` header and as A13/A14.

### `0015_money.sql` — **new migration**

- **`invoices.unit_id` is NOT NULL and there is no membership foreign key.** Liability attaches to
  the unit: a resident who moves out does not take the arrears with them, and a new occupant does not
  get a clean slate. `userId` on the wire is the flat's *current* occupant, resolved by the view for
  display only. — `DERIVED` (class diagram `{billing}` note, made structural)
- **`invoices.title` added — not in the ERD.** The dashboard renders `payments[].title` verbatim
  (`"Maintenance Fee - July 2026"`, `"Clubhouse Event Charge"`). Deriving it from type + period works
  for the first and not the second. — `AUDIT`
- **Three deliberate ERD deviations**, each recorded as `DECISIONS_NEEDED.md` D6: invoice numbers
  unique **per community** (the prefix defaults to `INV` for everyone, so a global constraint would
  stop the second community issuing its first invoice); **no `overdue` status** (derived in the view
  from due date and balance — a stored flag is correct only until the next midnight, and a value
  legal to store invites someone to store it); **nullable `payer_profile_id`** (an admin recording
  cash for a vacated flat has no payer to name). — `DERIVED`
- **The double-billing guard is a partial unique index**, not an API check:
  `(community_id, unit_id, billing_period_start) where invoice_type = 'maintenance' and status <>
  'void'`. A check in the service layer loses the race; an index does not. A repeat run reports every
  flat as `skipped` rather than failing. — `DERIVED`
- **Recording a payment is idempotent on `provider_reference`**, checked in the RPC *and* enforced by
  a unique index, so a replayed webhook returns the existing payment instead of double-crediting.
  — `DERIVED`
- **Overpayment is refused, not clamped.** Clamping accepts money and then loses it. `409`. — `PO`-adjacent, raised as A16
- **`outstanding_amount` is recomputed from the payment rows, never decremented**, and a CHECK
  constraint rejects any balance that disagrees with its own status. This is why money needs no
  optimistic concurrency: there is no read-modify-write to lose. — `DERIVED`
- **Nothing is ever deleted.** `void_invoice` cancels and keeps the invoice, its lines and its
  number; a number that disappears is a gap an auditor has to explain. Refused once any payment has
  succeeded. — `DERIVED`
- **Resident RLS is bounded by `issued_on >= residency.start_date`.** Liability follows the unit, so
  a flat's invoice history outlives its occupants — showing a new tenant the previous occupant's
  arrears would disclose one resident's debts to another. — `AUDIT`
- **`collection_summary` is a database aggregate**, not a loop in the service layer, and it sums
  outstanding *balances* rather than the amounts of unpaid invoices. — `DERIVED`

### `API.md` — new §9, three sections renumbered

- **§9 Money** documents all ten endpoints with full status-code tables. §9/§10 became §10/§11. — `PO` standing rule
- **`dashboard.collection` stops being a placeholder.** It now reads the same aggregate that serves
  `GET /invoices/summary`, so the home page and the collections screen cannot disagree about how much
  has been collected. — `DERIVED`
- **§1.7** records that the money endpoints carry no relative time and stay cacheable — `billPeriod`
  is a fixed calendar range, unlike `timeAgo`. — `DERIVED`
- **§1.10** records that optimistic concurrency has now slipped past two steps (four last-write-wins
  surfaces), and that money is the exception for a structural reason rather than because it was
  fixed. — `AUDIT`

### `openapi.yaml`

- Regenerated: **43 operations across 34 paths**, up from 33/26. `tests/test_openapi_spec.py` gained
  three more mounted-router assertions. — `PO` standing rule

### `DECISIONS_NEEDED.md`

- **A13** 🔴 no maintenance amount exists anywhere — what is it, and is it per-flat?
- **A14** 🟡 billing runs skip vacant flats, because nothing records ownership
- **A15** 🟢 a partially paid invoice reads `Unpaid`; its `amount` stays the full value
- **A16** 🟢 overpayment is refused rather than clamped
- **B11–B13**, **D6**, **E12–E15**, **F6** added; **E1** refreshed to `0010`–`0015` / 161 tests;
  **E7** struck through (the collection tile is real); **F4** re-dated to "before step 8". — `AUDIT`

### `FRONTEND_MEETING_AGENDA.md`

- **Item 11** — the money tiles are summed in the browser, so paging silently reports the total of
  one page. In rupees, plausibly.
- **Item 12** — **there is no way to bill anybody.** No screen creates an invoice, records an offline
  payment, runs a billing cycle or sets the rate. The largest single gap found so far.
- **Item 13** — a live rendering bug: `Payments.jsx:113` prints literal asterisks around the payment
  method. — `AUDIT`

---

## 2026-07-29 — Session 12: build step 6 (departments and staff); OpenAPI YAML made a standing rule

PO ruling: **a machine-readable API description is maintained alongside `API.md`, for every endpoint,
backfilled to cover everything already built.** — `PO`

### `openapi.yaml` — **new file**, generated

- **`docs/openapi.yaml` added**, covering all 33 operations across 26 paths — steps 3–6 plus the
  pre-existing auth and invitation endpoints. Generated by `backend/scripts/export_openapi.py` from
  the running FastAPI app. — `PO`
- **Generated, never hand-edited, and enforced.** `--check` fails when the file is stale and
  `backend/tests/test_openapi_spec.py` runs that check in the suite. The reasoning: a hand-maintained
  spec drifts the first time a field is renamed, and a *stale* spec is worse than no spec, because
  clients generate types from it and the drift becomes real code. — `DERIVED`
- **`API.md` is not replaced by it.** The generator can emit shapes; it cannot emit why a delete is
  really a deactivation, or which guard returns `409`. The two are complementary and both are
  required on every backend change. — `DERIVED`
- Two things the generator cannot know are injected by the script: the `servers` list (a deployment
  fact, so FastAPI omits it, and without it a generated client has no base URL) and per-tag
  descriptions. — `DERIVED`

### `API.md`

- **§8 "Departments and staff" added** — ten endpoints with full status-code tables; §"Not yet
  implemented" and §"Changelog" renumbered to 9 and 10, and step 6 removed from the former.
- **§1.3 gained a note** that path *placeholders* render `{membership_id}` in the generated spec and
  `{membershipId}` here. A placeholder is not part of any URL a client sends, so this is a Python
  parameter-naming artefact and not a second convention. Recorded so nobody "fixes" one to match the
  other. — `AUDIT`

### `DECISIONS_NEEDED.md`

- **A11, A12, B9, B10, D5 added; E1, E8, F4 updated.** New questions for the product owner (is a
  department delete really a delete? does removing staff deactivate?), the frontend team (the two
  category screens disagree; `head` is free text), and the ERD owners (should the column say
  `inactive`?).
- **F4 corrected rather than left standing**: it said optimistic concurrency was due "before step 6".
  Step 6 shipped without it, so the entry now says so and moves the target to step 7. An action item
  that quietly slips is worse than one that is renegotiated. — `AUDIT`

### `ADMIN_DASHBOARD_BUILD_PLAN.md`

- **Step 6's archive rule was wrong and is corrected.** It said *"a department cannot be archived
  while it owns unresolved complaints"*. The frontend blocks **deletion** on that condition and
  offers **deactivation as the escape hatch** — `Departments.jsx:569` renders a "Deactivate" button
  precisely when deletion is refused. Guarding deactivation too would remove the only remaining
  action and leave the admin stuck. The guard therefore belongs on `DELETE` alone. — `AUDIT`

### Code (logged here only because it decides design questions; git owns the history)

- **`0014_departments.sql` written, not applied.** Two `security_invoker` views
  (`department_overview`, `department_staff_overview`) and four RPCs. Three design decisions are
  recorded in the file's own header rather than only here, so they are visible to whoever reads the
  schema:
  1. **`head` is a name, not a link.** `departments[].head` is free text that also appears in
     `staff[]`. `0011` modelled the head as `staff_assignments.rank = 'head'` (R8), which is the
     better shape, so naming a head **promotes** the matching roster row — or creates one if nothing
     matches — demoting the incumbent in the same transaction. One source of truth, and the
     frontend's field still round-trips exactly. — `DERIVED`
  2. **Categories are upserted by name.** The two create screens disagree: one is a fixed checkbox
     list of six, the other a free-text box whose placeholder is *"e.g. Leaking pipes"* — a symptom,
     not a category. Rejecting unknown names breaks one screen. Cost: a typo becomes a category.
     Raised as B9. — `AUDIT`
  3. **Removing staff deactivates.** `complaints.assignee_label` records staff by name (C1), so
     deleting the row turns a past assignment into an unattributable string. — `DERIVED`
- **A view, not an RPC, for the department list.** A list endpoint needs filtering, ordering, paging
  and an exact count; PostgREST gives all four on a view for free, and an RPC would reimplement them
  as parameters. `security_invoker = true` is what keeps RLS applying to the caller — without it a
  view is a hole straight through RLS. — `DERIVED`
- **A precomputed `search_text` column** exists because the dashboard's one search box spans name,
  description, head, email, category names *and* staff names, which no combination of PostgREST
  filters across embedded tables can express. — `DERIVED`
- **Assignment counting uses `left(assignee_label, length(display_name)) = display_name`, not
  `ilike display_name || '%'`.** A staff name is user-supplied, so a `%` or `_` inside it would be
  read as a wildcard and silently overcount. `left()` is the exact prefix test the frontend's
  `startsWith` actually means. — `AUDIT`
- **`tests/conftest.py` added**, which makes `app.main` importable under pytest for the first time —
  `Settings` requires four Supabase values at import time. This is what allows the suite to assert
  that every router is mounted and that no endpoint is missing its auth dependency; both are failure
  modes with no other alarm. 111 tests pass (was 80). — `DERIVED`

---

## 2026-07-29 — Session 11: security work split off; first migration written

PO ruling: **the auth-adjacent security fixes (§1.1 privilege escalation, §1.2 unscoped `is_admin()`)
are owned by another developer, working in parallel.** This stream does not touch them. — `PO`

### `ADMIN_DASHBOARD_BUILD_PLAN.md`

- **§1 — ownership banner added**, marking §1.1/§1.2 as reassigned and §1.3 (`.venv`) as unowned and
  not auth-adjacent. — `PO`
- **§1.4 added — "Running two migration streams in parallel".** Splitting the work created two
  collisions that are cheap now and painful later, so both were decided rather than discovered:
  1. **Migration numbers reserved by range** — `0004`–`0009` to the auth stream, `0010`+ to the
     dashboard. Both streams would otherwise reach for `0004`, producing a merge conflict in schema
     *ordering*, which is the worst place to have one. — `DERIVED`
  2. **The dashboard does not inherit §1.2 while the fix is in flight.** Every new table carries
     `community_id` and its policies are community-scoped from the first line instead of reusing bare
     `is_admin()`. This is the finding that unblocked the stream: the ten new surfaces are not exposed
     by the unscoped-admin hole, so the dashboard need not wait on §1.2. Its cost is that this stream
     must not define `current_association_id()` — that name belongs to §1.2 — so `0010` uses
     `current_community_ids()`, set-returning because a person may belong to several communities.
     — `AUDIT`
- **Where the streams touch, they compose** — the fixed `handle_new_user()` owns the profile INSERT and
  defaults to `RESIDENT`; `0010`'s trigger owns every later change to `profiles.role`. Checked rather
  than assumed, because a collision here would have been silent. — `AUDIT`
- **§4 renumbered** (old step 1 reassigned; steps 4–10 became 3–9) and **§6 decision 1 closed** —
  additive-now/rename-later was *assumed and proceeded on* rather than blocked, on the grounds that it
  touches no auth code and reversing costs deleting one unapplied file. Recorded as an assumption, not
  a ruling. — `DERIVED`

### `CLAUDE.md`

- **Corrected the claim that `backend/` is "an empty placeholder for a future server".** It has been
  false since the FastAPI service landed, and it is the first thing anyone reads. Replaced with what
  is actually there, plus the fact that still makes the rest of the file true — the frontend is not
  wired to it and the demo runs with no server. — `AUDIT`

### Code (logged here only because it decides design questions; git owns the history)

- **`backend/supabase/migrations/0010_memberships.sql` written, not applied.** `community_memberships`
  + `unit_residencies` in ERD shape, backfilled from `profiles.role`/`association_id`/`apartment_id`,
  with `profiles.role` kept as a trigger-maintained compat column so no auth code changes.
- Two judgement calls in it worth preserving:
  - **`is_primary` is granted to exactly one occupant per flat on backfill**, the earliest-created.
    `unit_residencies_primary_uq` permits one; flagging every occupant primary would have made the
    index reject all but the first and **silently drop the rest of the household**. Only visible
    because the constraint and the backfill were written together. — `AUDIT`
  - **Flats are created from `profiles.apartment_id` on first reference**, since that free-text column
    holds codes for flats with no `apartments` row — the frontend never had a flat-creation step.
    Matches the find-or-create rule already promised in `FRONTEND_MEETING_AGENDA.md`. — `DERIVED`

### Deliberate zeros

- **`frontend/` — nothing changed.** Still the standing constraint.
- **ERD, class diagram, `design-of-components.md` — not edited.** `0010` adopts ERD *column* names
  (`community_id`, `unit_id`) while pointing at today's tables, so the ERD needs no revision and the
  eventual rename stays one mechanical migration.
- **No migration applied and nothing committed.**

### `0011_dashboard_core.sql` — step 2 (same session, after PO said "go ahead")

Ten tables covering the dashboard's non-money, non-amenity surfaces. Written, **not applied**. Four
assumptions are recorded in the migration header as `A1`–`A4` rather than only in this log, so that
anyone reading the schema meets them there.

**A correction to the build plan, found by opening the column instead of trusting the plan.**
`ADMIN_DASHBOARD_BUILD_PLAN.md` said R1's two partial unique indexes belonged on `apartments`, *"whose
current `unique (association_id, code)` has exactly the defect R1 describes."* It does not. R1 addresses
a **block-relative** label (`101` recurring per building) where a nullable `building_id` makes NULLs
distinct. `apartments.code` is community-wide by construction — the frontend builds it as
`` `${tower}-${flatNumber}` `` — so the block is already inside the string and per-community uniqueness
is correct. **Applying R1 would have loosened a working constraint, the opposite of its purpose.**
R1 is parked until the ERD's separate `unit_label` column exists. — `AUDIT`

**Assumptions, each isolated in one function or column so reversing is cheap:**

- **A1 — role vocabulary left undecided.** Staff `rank` and `job_title` are plain text, not members of
  `user_role`, because they are department-local descriptions that never reach a JWT. Open decision 2
  stays genuinely open instead of being settled by a side effect. — `DERIVED`
- **A2 — SLA tie-break** (open decision 3): category override wins, else lowest `sla_hours` among
  active claiming departments. One function, `resolve_category_sla_hours()`. Still a workaround. — `PO`
- **A3 — urgency multiplier: invented, and flagged as such.** R9 required `due_at` to derive from "the
  category SLA and urgency" but never said how urgency applies. Assumed high = ½, medium = 1×,
  low = 2×. **This is the one assumption in the file with no evidence behind it**, so it is now open
  decision 4 rather than a silent default. — `DERIVED`

**Three modelling decisions with reasons that are expensive to reconstruct:**

- **`staff_assignments.job_title` is stored, not derived from `rank`.** R8's rank/title split invites
  deriving the displayed string from the rank. The seed data proves the mapping is not a function:
  `dept-plumbing`'s head renders as `Supervisor` and `dept-facilities`' as `Manager` — same rank,
  different label. A derivation rule would silently rewrite one of them. — `AUDIT`
- **`complaints.department_id` is stored, not derived.** Re-resolving routing on read would make an
  edit to the category mapping retroactively rewrite where past complaints went. — `DERIVED`
- **`notices.category` stays free text while complaint categories are a table.** The difference is
  behavioural, not stylistic: a complaint category routes to a department and carries an SLA; a notice
  category is a display label with nothing attached. A table would add a join and a seeding step to
  buy nothing. — `DERIVED`
- **`complaint_categories.sla_hours` survives R5 as a nullable override.** C2 moved ownership to the
  join table, but an explicit value ends the ambiguity for that category outright — the escape hatch
  if the frontend meeting rules two owners legitimate. — `DERIVED`

**Also in the file:** module keys and defaults copied verbatim from
`frontend/src/data/onboardingModules.js` (a key that drifts silently disables a working feature, so
this is a copy of a contract, not a guess); assignment columns on `complaints` rather than
`work_orders`, per R9's resolution principle, named there as a conscious duplication;
`complaint_comments` kept separate from the event stream because collapsing an audit log into a
user-facing conversation yields either a leaky log or a useless one.

**Two bugs caught before they shipped**, both from writing the SQL out rather than describing it:

1. `complaint_due_at()` multiplied a `numeric` by an `interval`. Postgres defines `interval * float8`
   but has no `numeric * interval` operator, and an unqualified `0.5` is `numeric` — it would have
   failed on the first complaint insert. Fixed with explicit `::float8` casts.
2. **`ON DELETE SET NULL` on a composite FK nulls *every* column of the key**, including the `NOT NULL`
   `community_id`. Nine constraints were written that way, so deleting any referenced membership,
   category, department or flat would have raised a not-null violation instead of clearing the
   reference — and only in production, on the first time anyone removed a resident. Fixed with
   `on delete set null (the_pointer_column)`, which is **Postgres 15+ only**; noted in the file header
   since it is now a floor on the database version. — `AUDIT`

### `DECISIONS_NEEDED.md` — new

PO ruling: **collect every assumption made so far into a document teammates can answer directly.** —
`PO`

Created [`DECISIONS_NEEDED.md`](DECISIONS_NEEDED.md): 10 product decisions, 8 frontend items, 6
coordination items for the auth workstream, 4 for the ERD owners, 8 statements of surprising current
state, 5 ownerless work items, and an appendix listing every assumption with its reversal cost. Each
item states *what we assumed*, *why*, *cost if wrong*, and carries a blank `Answer:` line, so it can be
edited and committed rather than discussed and lost. Priority-tagged 🔴/🟡/🟢, and grouped by **who
answers** rather than by topic. — `PO`

### Step 5 — Complaints (`0013_complaint_events.sql` + six endpoints)

**A3 retracted, and the retraction is the finding.** `0011` assumed `due_at` = category SLA × an
invented urgency multiplier. Reading `createComplaintsSlice.js:5` showed the frontend **already** has a
concrete rule — High 24h / Medium 48h / Low 72h, from **urgency alone, ignoring the category**. So the
product carries **two independent SLA systems that never meet**: `departments[].slaHours` (4–48h) and
this urgency table. They have never collided only because complaints do not reference departments in
the frontend at all. A Low-urgency *security* complaint is due in 72h by one rule and 4h by the other —
**an 18× disagreement**. New precedence: category override → department SLA → urgency table, no
multiplier (urgency already picks the fallback; multiplying would count it twice). Which system should
win is a product question, raised as `DECISIONS_NEEDED.md` A1. — `AUDIT`

**Two gaps in `0011`, both found by reading the frontend rather than the resolutions:**

- **`complaint_events` was never created.** R9 resolved "management notes" with *"no column —
  `complaint_events` already has `note`"*, but that table existed only in the ERD. The frontend keeps
  `comments[]` and `timeline[]` as **separate** things and the admin's "Resident-visible Update" box
  writes the timeline. Now created, and **append-only structurally** — no `UPDATE`/`DELETE` policy, so
  it cannot be edited even by an admin. R9's distinction between an audit stream and a conversation is
  now enforced by Postgres rather than by convention. — `AUDIT`
- **`complaints.location` was missing** — a free-text "where in the building", distinct from the flat
  the complaint belongs to. — `AUDIT`

**Design decisions:**

- **`reopened`/`closed` render as `Pending`/`Resolved`.** The frontend's select has three options and
  `reopenComplaint` sets status back to `Pending` plus a counter. The database keeps a distinction the
  UI does not show, rather than discarding it to make the mapping symmetrical — so `to_wire` round-trips
  but `to_storage` deliberately does not. — `DERIVED`
- **`due_at` is writable, not purely derived** — `Complaints.jsx` has a `datetime-local` input for
  "Expected Resolution", so the admin can override the computed deadline. — `AUDIT`
- **`isBreaching` = deadline passed **and** still open.** A resolved complaint that took too long is
  *late*, not breaching; the tile counts work outstanding now. Computed server-side so every screen
  agrees on the definition. — `DERIVED`
- **Read state is per person**, from a receipt row, not a flag on the complaint. The frontend's single
  `hasUnreadUpdate` boolean cannot represent an admin and a resident having seen different versions.
  — `DERIVED`
- **Attachment bytes never pass through the API** — the client uploads to Supabase Storage and
  registers the path. Requires a **private** bucket `complaint-attachments`; a public one would make
  every complaint photo world-readable by URL, bypassing RLS entirely. Signing failures degrade to a
  null URL rather than failing the request — one broken attachment must not take down the complaint.
  — `DERIVED`
- **`update_complaint` and `add_complaint_comment` are RPCs**, per the step-4 finding: a status change
  must not be able to land without its timeline entry. An audit trail with holes is worse than none,
  because it looks complete. — `DERIVED`

**Tests: 57 → 80**, adding the vocabulary mapping (including that an unknown status is *rejected*
rather than silently becoming `pending`, and that the wire round-trip is stable).

### Step 4 — People (`0012_people.sql` + six endpoints)

**The finding that shaped the step: PostgREST has no client-side transaction.** Each
`.table(...).insert()/.update()` from supabase-py is its own transaction, so any FastAPI operation
spanning two tables can half-succeed. Approving a registration is exactly that — mark the request
approved *and* mint the invitation — and a crash between them leaves a request approved that nobody
can act on, with no way to fix it from the UI. **Atomicity through PostgREST requires a Postgres
function**, so approve / reject / deactivate live in SQL and are called via RPC. Each takes a row lock,
so two admins clicking Approve at the same instant serialise and the second gets a 409 rather than a
duplicate invitation. This generalises: every future multi-table write is an RPC. — `AUDIT`

**`SECURITY DEFINER` means RLS does not run.** Each of the three functions performs its own
authorization check as its first statement. A `SECURITY DEFINER` function without an explicit check is
a hole with an API in front of it. — `DERIVED`

**Not everything became an RPC, deliberately.** `PATCH /residents` also writes two tables but stays
plain: a partial failure leaves some fields updated and others not, which the admin sees and retries.
There is no invariant between those two writes; approval has one. The distinction is what a partial
failure *costs*, not how many tables are touched. — `DERIVED`

**Three product decisions:**

- **Approval mints an invitation rather than creating an active account**, because the invite token is
  a mandatory second factor (standing ruling). This differs from the demo, where `acceptRequest`
  creates an `Active` resident immediately — but the admin still sees the request leave the pending
  list, which is what the screen reacts to. — `PO`
- **"Remove resident" deactivates; there is no hard delete.** Complaints, invoices and payments
  reference the membership, so deleting the row would cascade them away or fail outright. — `DERIVED`
- **An admin cannot remove their own membership** (409). There is no recovery path in the product from
  locking a community out of its own dashboard. — `DERIVED`

**A live frontend bug, found while building approval.**
`createPendingRequestsSlice.js:36` builds `` `${tower}-${flat}` ``, but the seeded requests in
`data/pendingRequests.js` already store `flat: 'C-505'` — so approving a seeded request produces
**`C-C-505`**, a flat that does not exist, while a form-submitted request (bare `505`) produces the
correct `C-505`. Two code paths disagree about what `flat` holds. Absorbed by `app/domain/units.py`
and raised as **agenda item 8** — the first item on that list that is a bug rather than a design
mismatch. — `AUDIT`

**Schema decisions:**

- **`community_memberships.designation`** — President / Secretary / Treasurer / etc. is a **third
  axis**, distinct from `role` (what the system permits) and staff `job_title` (what a worker does).
  Free text, no check constraint: the list is a frontend display vocabulary that will grow, and a
  constraint would turn every addition into a migration. — `DERIVED`
- **`profiles.email` backfilled from `auth.users`**, which this migration can read as table owner.
  **Keeping it current for new users belongs in `handle_new_user()`, which the auth workstream owns**,
  so it is not edited here — a coordination item, not a silent gap. Their fix to that function does not
  otherwise collide with ours: invite redeem sets the role explicitly afterwards
  (`invitation_service.py:187`), so dropping the client-supplied metadata role is safe for our paths.
  — `AUDIT`
- **One *pending* request per phone per community**, partial index — so a rejected applicant may apply
  again and both attempts survive in the history. — `DERIVED`
- **Custom SQLSTATEs `HB403`/`HB404`/`HB409`** rather than message matching, so rewording a message
  cannot silently turn a 403 into a 500. Postgres' own constraint messages are **not** forwarded to
  callers — they can quote a row value. — `DERIVED`

**Refactor:** `CamelModel`/`Page` moved to `domain/common_schemas.py` and `display_role`/`parse_instant`
to `domain/roles.py` / `core/formatting.py`, once a second surface needed them. A module named for one
screen is the wrong home for the base class every screen inherits.

**Tests: 14 → 57.** New coverage for flat-code normalisation (including that it is idempotent — the
exact shape of the frontend bug), SQLSTATE mapping (including that Postgres text never leaks to a
caller), and the formatting contract (the exact strings from `complaints.js` and `notices.js`, plus
the negative-duration and local-day-boundary cases).

### `API.md` — new, and now a standing rule

PO ruling: **every backend implementation also produces API documentation in `docs/`, to current
industry standards, including error and other status codes — as a standard rule from now on, whether
or not it is asked for.** — `PO`

Created [`API.md`](API.md): conventions (versioning, auth, the error envelope, the full status-code
table, pagination, caching, rate limiting, date handling, optimistic concurrency) followed by every
endpoint — the four new dashboard reads **and** the pre-existing auth and invitation endpoints, which
had never been documented. Includes a "not yet implemented" table so the frontend team can see what is
coming and in what order.

Two things the document had to admit rather than paper over: `/auth/*` still describes phone/SMS OTP
because that is what the code does, even though the ruling is OAuth; and **nothing is rate-limited**,
including the two unauthenticated secret-guessing surfaces (`/auth/otp/request`, `/auth/redeem`). Both
are flagged in place. — `AUDIT`

### Step 3 — the read-only shell (endpoints)

Four endpoints in `backend/app/`, following the existing layering. Imports verified, routes verified
via the generated OpenAPI schema, **all 14 existing tests still pass.**

**Three defects found by running the code rather than reading it:**

- **The app would not have started on Windows.** `zoneinfo.ZoneInfo("Asia/Kolkata")` raises
  `ZoneInfoNotFoundError` at *import time* unless `tzdata` is installed, and it is not. Replaced with a
  fixed `UTC+05:30`. This is not a workaround: India has never observed daylight saving, so the offset
  is exactly correct year-round; `tzdata` becomes a genuine dependency only if a DST-observing
  community is ever supported. — `AUDIT`
- **Three error shapes existed on the wire, not one.** `register_exception_handlers` documented itself
  as handling uncaught exceptions but registered only `AppError` — so validation failures returned
  FastAPI's `{"detail": [...]}` and crashes returned `{"detail": "Internal Server Error"}`. A client
  cannot branch generically across three shapes. Added handlers for `RequestValidationError`,
  `StarletteHTTPException` and bare `Exception`. The 500 message is fixed text on purpose: an
  exception string can carry a table name or a connection string. — `AUDIT`
- **`residents[].email` is a real gap.** `profiles` has no email column; the address is in `auth.users`
  behind the service-role key. Returned `null` and documented, rather than silently dropping a field
  the Residents screen renders. `profiles.email` lands in step 4. — `AUDIT`

**Conventions set here, deliberately, because every later surface copies them:**

- **`Page` envelope identical whether or not there is data** — `{items: [], total: 0}` with HTTP 200,
  never a 404. Directly serves `FRONTEND_MEETING_AGENDA.md` item 7: the dashboard has never rendered an
  empty state, and one shape to design against is the cheapest help available from this side. — `DERIVED`
- **`Cache-Control: no-store` applied per endpoint, not as middleware**, so responses without a
  relative time stay cacheable. Every such DTO also carries the raw ISO instant, so `no-store` can be
  dropped per endpoint as screens adopt client-side formatting. — `DERIVED`
- **Two `timeAgo` vocabularies, on purpose.** Notices render `Today`/`1w ago`; complaints render
  `2h ago`. Two formatters rather than one with a flag, because the two frontend lists genuinely
  disagree and a single formatter would have to pick a winner. — `AUDIT`
- **`/auth/*` stays snake_case while new surfaces are camelCase.** The frontend reads camelCase and
  cannot change; the auth DTOs are being edited in parallel by the security workstream, so converting
  them here would be a drive-by edit to someone else's in-flight work. Recorded in `API.md` §1.3 as a
  seam with a fix, not left implicit. — `DERIVED`
- **`pendingRequests` and `collection` are hardcoded zeros** until steps 4 and 7, present from day one
  so the response shape never changes, and marked as placeholders in `API.md` rather than passing for
  real counts. — `DERIVED`
- **Flat codes are resolved to ids by a second query, not a PostgREST embed.** The path from a
  membership to a flat runs through `unit_residencies`, whose FKs are composite; PostgREST does not
  reliably embed across composite keys, and a silently-empty embed is worse than an extra round trip.
  — `AUDIT`

### Deliberate zeros, step 2

- **`frontend/` — nothing changed.**
- **ERD / class diagram / component design — not edited.**
- **R1 not applied** (see above), and `apartments`' existing constraint left alone.
- **Nothing applied, nothing committed.** Neither migration has been run — there is no Postgres,
  `psql`, Supabase CLI or Docker on this machine, so both files are reasoned through but **unverified
  by execution**.

---

## 2026-07-29 — Session 10: scope narrowed to the admin dashboard; the existing backend found

PO rulings: **ignore login and registration**, assume done; work on the **admin dashboard only**; code
goes in `backend/`, docs in `docs/`; **do not touch `frontend/` at all** — conflicts beyond the
backend's reach go to a document for the frontend meeting. — `PO`

### `backend/` is not the empty placeholder `docs/CLAUDE.md` describes

It contains a working, cleanly layered FastAPI service — `core/supabase_client.py` as the single
client factory with three trust levels, `domain/schemas.py` DTOs deliberately separate from row
shapes, `require_role(...)` guards — plus three applied migrations (`0001_init`, `0002_rls`,
`0003_access_token_hook`). Planning had been proceeding as though none of it existed. — `AUDIT`

### C3 retracted

`IMPLEMENTATION_PLAN.md` §2 argued for **no bespoke API server** — views and RPC instead. **Written
without knowing this service existed, and wrong for this team.** The FastAPI layer is the better
answer to the problem C3 was about: it is where the frontend's exact response shapes get composed,
and unlike a Postgres view it can do that without pushing display concerns into the schema. — `AUDIT`

### Three findings that outrank the dashboard

| # | Finding | Severity |
|---|---|---|
| 1 | **`handle_new_user()` reads the role from `raw_user_meta_data`**, which is client-supplied — `signUp({options:{data:{role:'ADMIN'}}})` yields an ADMIN profile, and the access-token hook then mints an ADMIN claim that both RLS and the FastAPI guards trust. Held shut today only by `should_create_user=false` on the OTP path; **the OAuth switch opens it**, because OAuth creates users by design. | **Critical** |
| 2 | **`is_admin()` is global, not per-community.** `profiles_self_select` and `associations_admin_write` use it unscoped, so any admin reads every profile in the database and writes every association. Admins are exactly the role this dashboard serves, so all ten new surfaces would inherit the hole. | **High** |
| 3 | **`backend/.venv` is committed** — 4,100+ tracked files including Windows `.pyd` binaries. `.env.example` is correctly committed and holds no secrets. | Medium |

Both 1 and 2 are step 1 of the build, before any feature work.

### The schema in the database is not the schema in the ERD

`associations`≠`communities`; role and placement live on `profiles` rather than in
`community_memberships` / `unit_residencies`; the role enum has `TECHNICIAN` where the ERD has
`worker`. **The dangerous one: `units` means a block in the live DB and a flat in the ERD — exact
opposites.** A query written from the ERD returns the wrong entity with no type error. — `AUDIT`

Resolution: **additive now, rename by agreement** — dashboard tables take ERD names, the four live
tables stay, a naming map is published, and the rename stays one mechanical migration. But
`community_memberships` lands in step 2 rather than later, because every dashboard table needs an
actor FK and pointing those at `profiles` means repointing all of them afterwards. **Coordination cost
is zero:** `profiles.role` is kept as a trigger-maintained compat column, so the access-token hook,
`jwt_role()`, `is_admin()` and every existing guard keep working with **no auth code changed**. — `DERIVED`

Also worth recording: the live `invitations` table already stores both a `token_hash` and a
`code_hash` — arriving independently at exactly what R2 proposed. A point in favour of the working
schema.

### Two withdrawals reinstated, because the premise moved again

With `frontend/` now strictly off-limits, **R24** (`timeAgo` in responses, and the un-cacheable
response class it forces) and **R23** (label *and* id on every DTO) come back. **C1** free-text
assignee is accepted as `assignee_label` plus a nullable FK. All three are on the meeting agenda
rather than being silently absorbed. — `DERIVED`

**C2 has now had three positions** — join table → one-to-many → join table. Not circular: it turns on
whether the UI can be changed, and that premise moved twice. With the multi-select unchangeable, the
schema must accept what the UI emits. **The SLA ambiguity remains genuinely unresolved** — "lowest
`sla_hours` wins" is a workaround, and it is agenda item 2. — `AUDIT`

### `docs/ADMIN_DASHBOARD_BUILD_PLAN.md` — **new file**

Ten steps. Steps 1–3 ship no endpoints: security fixes, `0004_memberships.sql`,
`0005_dashboard_core.sql`. Then the ten surfaces in dependency order. Follows the existing service's
conventions rather than proposing new ones.

### `docs/FRONTEND_MEETING_AGENDA.md` — **new file**

Seven items only, each with what the frontend does today, why it is a problem, what we need, and
**the cost of doing nothing** — because for several of them doing nothing is a legitimate answer. Also
lists five things that looked like conflicts and turned out to need nothing from them, so the meeting
is not spent on those.

### Deliberate zeros

- **No code written, no migration applied, no artifact edited.** The three security findings are
  documented, not fixed — fixing them touches auth code the PO scoped out, so they need a decision
  first.
- **`frontend/` untouched**, and now permanently so.

---

## 2026-07-29 — Session 9: the demo reframe, and the implementation plan

The PO disclosed that the frontend was **deliberately built on seeded dummy data** so the team could
demonstrate how much work had been done. — `PO`

**This changes the operative constraint from "never change the frontend" to "never break the demo",**
and those are very different rules. Earlier sessions assumed the first one and paid for it. — `AUDIT`

### Standing instruction added

Every proposal from now on is checked against **all five artifacts plus Supabase** — frontend, ERD /
DBML, class diagram, design of components, and whether a Supabase feature removes the need for custom
code — and the impact on each is stated, **even when the request does not mention them**. "No impact"
must be said, not omitted; a silent gate reads as an unchecked one. — `PO`

### `docs/IMPLEMENTATION_PLAN.md` — **new file**

Nine phases (0–8), each ending with the demo running. Two seams — a client repository module with
`mock` and `supabase` implementations, and `security_invoker` views plus `SECURITY DEFINER` RPC on
the server — and **no bespoke API server**, which is what resolved C3. — `DERIVED`

### Three earlier compromises withdrawn

All three existed only because the frontend was assumed unchangeable. — `AUDIT`

| Was | Now | Why it was wrong |
|---|---|---|
| **R24** — ship `timeAgo: "2h ago"` beside the ISO instant | **Dropped.** Instants only; the frontend formats. | It forced `Cache-Control: no-store` on an entire response class and put the server's clock and locale into a client concern — a real architectural cost paid to preserve a seed convenience. |
| **R23** — every entity carries label *and* id, permanently | **Transition measure**, removed in Phase 8. | Freezing `assignee: "Ramesh - Plumber"` into the API would have made the demo's shortcuts permanent product debt. |
| **C1** — nullable FK plus `assignee_label`, indefinitely | **Interim only**; closed in Phase 6 by `auth.admin.createUser` shadow accounts. | Supabase can create an account for someone who never signs in, turning a permanent retreat from referential integrity into a two-phase migration. |

### One recommendation reversed on the merits, not on the reframe

**C2 — complaint categories.** I proposed a `department_categories` join table because the UI's
multi-select permits two departments to claim "Plumbing". Reversed to **one-to-many**: with N:M,
*"which department's SLA applies to this complaint?"* has no answer, and the join table would push
that ambiguity into every complaint ever filed. Smaller schema and smaller frontend change than the
join table. Still a product decision — it is question 1 in §8, and the join table stays available if
a category genuinely needs two owners. — `AUDIT`

### Demo continuity — raised because nobody had

Two mechanisms break silently under a real backend and needed to be on the record before Phase 5, not
after a demo is lost: the hardcoded demo logins (`9876543210` / `9999988888`, with the OTP unchecked)
do not survive OAuth, and `mock` mode must stay a **supported build** rather than scaffolding to
delete — it is the offline demo, the fallback when the Supabase project is down mid-presentation, and
the only thing that keeps a two-implementation seam honest. Resolution: `supabase/seed.sql` rebuilds
the demo dataset server-side and the presenter's real Google account is seeded as its admin. — `DERIVED`

### Deliberate zeros

- **No artifact was edited and no code was written.** Phase 1 is where the ERD, class diagram and
  component design change, and it has not started.
- **No frontend work was done.** Five frontend work packages are *specified* in §7 for the frontend
  team; the rule that we do not touch `frontend/src/` without them is unchanged and was strengthened,
  not relaxed, by the demo framing.
- **Eight decisions left open** (§8) rather than decided by default.

---

## 2026-07-29 — Session 8: resolving the audited conflicts

The product owner asked for the conflicts catalogued in `MILESTONE1_ARTIFACT_ISSUES.md` to be
resolved one by one. — `PO`

### `docs/CONFLICT_RESOLUTIONS.md` — **new file**

One resolution (R1–R35) for every issue in the audit, each naming its decision, its cost against the
v1 ERD as submitted, and the person who has to make the edit. **Nothing was applied to any artifact**
— the ERD, class diagrams and component design are maintained by other people, so this file proposes
and does not change. — `DERIVED`

Three constraints were carried in from earlier rulings and every resolution had to satisfy all three:
zero frontend conflicts, minimal change to the three artifacts, and resolve in the layer that owns
the truth. — `PO` (restated)

Net effect on the v1 ERD if all are accepted: **+5 tables, ~33 columns, 0 tables deleted, 0 frontend
files changed.** Eight tables that a less careful pass would have added were resolved without one —
recorded in §6 of the file, because "what we chose not to add" is the part that is expensive to
reconstruct later.

### Decisions worth flagging out of the 35

| Decision | Why it is worth reading |
|---|---|
| **R3** — use `updated_at` as the optimistic-concurrency token instead of adding `version` columns | Zero schema change. Conditional on a `BEFORE UPDATE` trigger on every table and on the client echoing the timestamp at full microsecond precision — without both, the check silently passes when it should fail. — `DERIVED` |
| **R4** — composite foreign keys, not a denormalized column plus a trigger | A denormalized `community_id` kept in sync by a trigger is a rule someone can forget; `foreign key (parent_id, community_id) references parent (id, community_id)` makes a divergent row impossible to insert. Applied to the 6 child tables read as their own list; the rest keep parent-join policies. — `AUDIT` |
| **R5** — `complaint_categories` table | One change resolves three audit items at once: free-text categories, the unenforceable department-deletion rule, and the departments SLA gap. — `AUDIT` |
| **R7** — the audit was corrected | I had written that the QR pass "has nowhere to live". The real finding is narrower and better evidenced: `createVisitorsSlice.js` mints a `qrToken` **independent of** the `securityCode` and the gate matches on both, so two digests are needed. A QR that merely encoded the access code would have needed no column at all. — `AUDIT` |
| **R14** — maintenance blocks live in `amenity_booking_occurrences`, not a new table | **Forced, not preferred.** A PostgreSQL exclusion constraint cannot span two tables, so a block in a separate table could not participate in the existing no-overlap constraint and a booking could be created inside a maintenance window. Costs one nullability change on `amenity_booking_series.unit_id`, guarded by a CHECK. — `DERIVED` |
| **R17(c)** — residency, not role, grants resident capabilities | An active `unit_residencies` row grants the resident portal; `community_memberships.role` grants staff and admin powers. Resolves the "security supervisor who lives here" problem at zero cost, keeps the one-membership-per-person-per-community index intact, and collapses five class-diagram subclasses (R29). It was already how the admin-who-is-also-a-resident case worked — it had just never been written down. — `AUDIT` |
| **R21** — find-or-create units on first reference | Chosen over a frontend units-per-block step because the frontend is not ours to change. Two accepted costs: the unit list is only as complete as what has been referenced, and it makes R1 load-bearing — **R1 must land first** or the second block's "101" collides with the first block's. — `DERIVED` |
| **R24** — keep `timeAgo` alongside an ISO instant | The one resolution recorded as unsatisfactory. Server-side relative-time formatting is wrong on principle, but removing it is a frontend change and the zero-conflict constraint forbids that. **Consequence that must not be lost: any response carrying `timeAgo` is un-cacheable** — `Cache-Control: no-store`, never behind a CDN. Delete it the day the frontend adopts `submittedAt`. — `DERIVED` |
| **R16** — 13 tables tagged rather than deleted or built | The 12 orphans plus `community_registration_requests`, which the OAuth ruling orphaned — it models operator review and OTP, and founding is now self-serve. Tagging converts an unexamined surface into a dated decision. — `AUDIT` |

### §8 added — conflicts the resolutions themselves create

The PO asked whether implementing the resolutions would create conflicts. Auditing the "zero frontend
conflicts" claim against `frontend/src` instead of trusting it found **that claim was false in two
places**, both mine. — `AUDIT`

| # | Conflict | Consequence |
|---|---|---|
| **C1** | `complaints.assigned_to_membership_id` (R9) cannot be satisfied. The FK chain requires every assignable person to hold an auth account; department staff have none, and `Complaints.jsx:175` is a **free-text** assignee field with no referent at all. | R9 revised: nullable FK plus `assignee_label text`. A deliberate, temporary retreat from referential integrity — recorded as one rather than discovered later. Shadow `auth.users` rows are the real fix, deferred to when staff dashboards exist. |
| **C2** | Complaint categories are **many-to-many** in the UI — `Departments.jsx:211` lets two departments both select "Plumbing" — but R5 made `department_id` single-valued with a unique name. | +1 join table `department_categories`. Six new tables, not five. R5's other two wins survive. |
| **C3** | R5, R17a, R21, R23 and R24 all assume a server layer shapes the response. Direct `supabase-js` access to PostgREST has none — which conflicts with the standing "use Supabase as much as possible" direction. | Resolvable Supabase-natively as **reads through `security_invoker` views, writes through `SECURITY DEFINER` RPC**. Needs an explicit architecture decision. R3 turns out *not* to need it: `PATCH ?id=eq.X&updated_at=eq.Y` returns zero rows on a stale token natively. |
| **C4** | Applying these to v1 would leave **three** schema descriptions — v1, v1-plus-resolutions, and our unagreed 63-table draft, which resolves many of the same issues differently. | Pick one destination before applying anything. Fold into the v2 draft, or apply to v1 and delete the draft. Not both. |
| **C5** | The zero-conflict claim is measured against the frontend **as read on 2026-07-29**, and the frontend is moving. | Re-run the C1 and C2 checks immediately before applying. |

Four smaller ones (C6–C9): R28's nullable `unit_id` drops staff invites into the same
NULL-distinctness hole R1 exists to avoid; R14 silently does nothing unless the exclusion
constraint's predicate is edited in the same migration; R28 gives staff a weaker invite than the
PO-mandated resident 2FA token, currently as a side effect rather than a decision; and R21's label
parsing can land an apartment admin in the standalone branch.

Also second-order: `DepartmentDetail.jsx:217` recovers the staff name with
`assignee.split(' - ')[0]`, so the `" - "` format is load-bearing — R8 splitting `role` into `rank`
and `job_title` breaks that reverse lookup unless the API re-joins them exactly.

### Deliberate zeros

- **No artifact was edited.** Not the ERD, not the class diagrams, not the component design, not
  `frontend/`. The resolutions are proposals addressed to their owners.
- **No table was proposed for deletion**, including the ones no requirement asks for.
- **Six items were left explicitly unresolved** (§8) because they are product decisions, not design
  ones — the community address, one-residency-or-many, the Settings toggles, and the fate of work
  orders, workforce and policies. Left open rather than decided by default.

---

## 2026-07-29 — Session 7: verifying the restore against the submitted originals

The product owner supplied the two milestone-1 source files (`design-of-component.txt`,
`er-dbml.txt`) so the session-6 revert could be checked against them rather than trusted. — `PO`

### Verification result

| Supplied file | Repo file | Result |
|---|---|---|
| `er-dbml.txt` | `erd/homebandhu-v1-milestone1.dbml` | **byte-identical** — `diff` clean. The repo already carried the original faithfully; no action needed. |
| `design-of-component.txt` | `design-of-components.md` | **one line differed** — see below. |

### `docs/design-of-components.md` — one restore error corrected

| Change | Why |
|---|---|
| *"Provide separate entry points for residents and association administrators."* → *"Provide separate entry **and login flows** for residents and association administrators."* | The session-6 revert was done **by hand**, because this file is untracked and git had no baseline to restore from. Four of the five reverted edits were exact; this one was not — I reconstructed the sentence from memory and got it wrong, weakening "separate entry and login flows" into "separate entry points". Now restored verbatim and verified with `diff`. **Lesson: a hand-reconstructed revert is a guess until it is diffed against the original.** — `AUDIT` |

The corrected line matters beyond accuracy: *"separate entry and login flows"* is a stronger claim
than *"separate entry points"*, and it is precisely the claim the single-entry OAuth decision
supersedes. Weakening it would have quietly hidden a real conflict.

### `docs/erd/README.md` — **new file**

States which of the two `.dbml` files is authoritative (`homebandhu-v1-milestone1.dbml`, the
teammates') and which is our unagreed working draft (`homebandhu.dbml`, 63 tables). Added rather
than renaming the draft, because the name is referenced from `BACKEND_PLAN.md` and several historical
entries in this log — a rename would have silently invalidated those references. A README fixes the
ambiguity without breaking anything. — `DERIVED`

### `docs/MILESTONE1_ARTIFACT_ISSUES.md` — **new file**

Issue audit of the four milestone-1 artifacts against each other and against the frontend. Recorded,
**not fixed** — the ERD, class diagrams and component design are maintained by other teammates.

Principal findings:

| Finding | Note |
|---|---|
| **The ERD and class diagram agree with each other and both disagree with the component design and the frontend.** They were written together; the gap is with the product, not between themselves | Reframes the whole reconciliation: this is not a diagram-vs-ERD problem. — `AUDIT` |
| **`units_community_label_uq` is `(community_id, unit_label)`** — "Flat 101" can exist once per community, so a second block can never have one | Ranked the #1 fix. It is a correctness bug that blocks the most common deployment shape. — `AUDIT` |
| **`resident_invites` forbids storing plaintext tokens and provides no digest column** | The table forbids the only mechanism it offers; the invite flow is unimplementable as specified. — `AUDIT` |
| **Departments: 6 of 6 component-design requirements have no column. Complaints: 9 requirements, 0 columns** | Two of the ten admin surfaces cannot be built against v1. — `AUDIT` |
| **12 of 48 tables have no requirement and no UI** — work orders (5), workforce (5), policies (2) | A quarter of the ERD. Not necessarily wrong, but currently an unexamined surface rather than a decision. — `AUDIT` |
| **No `version` column anywhere; no `community_id` on child/event tables** | Both are cheap now and invasive later — the second changes every RLS policy already written. — `AUDIT` |
| **Class diagram models role as inheritance** — five `CommunityMembership` subclasses | Role is state, not type: promotion would require changing an object's class. Also makes the resident-who-is-also-security-supervisor unrepresentable. — `AUDIT` |
| **Class diagram has behaviour without state** — `Complaint.reopen()` and `escalate()` exist with no `reopenCount`, escalation flag or assignee to record their effect | — `AUDIT` |
| **Component design §10 claims a `notifications` collection that does not exist** in `frontend/src/store/slices/` | Verified by directory listing. — `AUDIT` |
| **Component design §2 collects an admin "unit number" while creating only blocks and villas** | The document does not notice it never creates the flat that number refers to — the origin of the missing-inventory problem. — `AUDIT` |

### Deliberate zeros

- `erd/homebandhu-v1-milestone1.dbml` — verified identical to source, **no change needed**.
- `class-diagram/*` — audited, **not edited**; issues recorded in the new document instead.
- `frontend/` — **untouched**, as in every prior session.

---

## 2026-07-29 — Session 6: reverting shared artifacts, and the admin dashboard plan

### Reverted — our edits backed out of the artifacts other teammates now own

**Ruling.** The ERD, class diagrams and component design are being maintained by other teammates.
Our edits come out so the two efforts do not collide. — `PO`

| Artifact | Reverted to | How |
|---|---|---|
| `class-diagram/homebandhu-domain.puml` | the staged (teammates') version | `git restore` from the index |
| `class-diagram/homebandhu-architecture.puml` | same | same |
| `class-diagram/README.md` | same | same |
| `class-diagram/*.svg`, `*.png` (4 files) | same | same — the regenerated renders are gone with the source edits, which is correct: a render must match its source |
| `design-of-components.md` | as supplied | the five sentence-level additions removed by hand (git has no baseline — the file is untracked) |
| `erd/homebandhu.dbml` | pre-session-4 state | the two "ten modules" notes reverted to "nine" by hand |

Everything was copied to a scratchpad backup before any revert, so nothing is unrecoverable.

**Two things deliberately NOT reverted**, because they are our own working documents rather than
shared artifacts: `BACKEND_PLAN.md` and `CHANGE_LOG.md`. Reverting `BACKEND_PLAN.md` to its staged
state would discard every planning session. — `DERIVED`

**Known cost of the revert, accepted:** the "nine feature modules" count in `homebandhu.dbml` is
**wrong** — `onboardingModules.js` defines ten. The correction was backed out along with everything
else. It is restated in `ADMIN_DASHBOARD_PLAN.md` and `ADMIN_REGISTRATION_FLOW.md` so it is not lost,
but whoever owns the ERD needs to apply it. Reverting a correct fix is the price of not colliding;
recording that it was a correct fix is how it gets re-applied rather than re-discovered. — `AUDIT`

`docs/erd/homebandhu.dbml` and `docs/design-of-components.md` are **untracked**, so they were never
shared through git in the first place — the collision risk was always confined to the class-diagram
files. Noted so nobody assumes the revert was broader than it was.

### `docs/ADMIN_DASHBOARD_PLAN.md` — **new file**

The admin dashboard backend plan: the ten nav surfaces and what each reads and writes, eight
cross-cutting decisions, a seven-phase build order, per-surface endpoint contracts, and the
reverse-mismatch section (UI implying a data model that does not exist). — `DERIVED`

Findings worth flagging outside the document:

| Finding | Why it matters |
|---|---|
| **The Admins page conflicts with the schema.** The ERD carries a partial UQ of one active admin per community and the class diagram states it as an invariant, but the frontend has an Admins *list* page that adds unlimited admins | Resolved by separating *owner* (one, `communities.active_admin_membership_id`) from *administrator* (many, `role = 'admin'`). Both artifacts were answering different questions rather than one being wrong. Raised as request 1 in §7, not applied. — `AUDIT` |
| **`departments[].staff[].role` mixes two axes** — `"Supervisor"` is a rank, `"Technician"` is a job title | Exactly the collapse §3.1 and §3.10 were written to prevent, now found in live seed data rather than in a document. — `AUDIT` |
| **Invoice liability differs between layers.** The frontend attaches payments to `userId`; the ERD attaches invoices to `unit_id` so debt does not follow a departing resident | A semantic disagreement, not a mapping detail — raised as request 4. — `AUDIT` |
| **Settings is a stub** with no persistence, whose four toggles imply automated billing and late-payment fines that exist in no table | Those are a phase, not settings. Recommend shipping Settings against `community_settings` only. — `AUDIT` |
| **Onboarding promises module editing that does not exist** — step 3 says features can be changed later in Settings; no such control exists | A small, visible broken promise on day one. — `AUDIT` |

### Deliberate zeros

- `docs/frontend-documentation.md` — read for the endpoint summary, **not edited**. It is the
  frontend team's document.
- `frontend/` — **untouched**, as in every prior session.

---

## 2026-07-29 — Session 5: OAuth replaces phone/OTP as the authentication method

**Ruling.** The backend team trialled several OTP implementations and concluded OAuth is the better
fit. Authentication is now OAuth; the phone-and-code entry path is retired. — `PO`

**New entry flow, as agreed in the 2026-07-29 morning meeting:** authenticate → check whether the
account holds an active membership → if yes, go to the dashboard for its `displayRole`; if no, show
a new two-button chooser (*Join a community* / *Create a community*). *Create a community* enters the
existing five-step admin registration; *Join a community* enters the resident path. — `PO`

### `docs/ADMIN_REGISTRATION_FLOW.md` — redrafted

| Change | Why |
|---|---|
| **Step 0 rewritten** from a phone-and-code entry to OAuth sign-in plus a `POST /auth/session` hand-off that returns the registration branch | Direct consequence of the ruling. The hand-off is kept rather than letting the client hold the session outright, so the refresh credential still lands in a `Secure; HttpOnly` cookie per §3.7 — that decision was independent of how the user authenticates and survives the change. — `DERIVED` |
| **New §3, the `/get-started` chooser**, specified as pure navigation that sends nothing to the server | The button a user presses is not a claim of authority. Each flow authorises itself when it submits, so the chooser can stay a client-side branch with no endpoint of its own and no trust attached. — `DERIVED` |
| **The short-lived onboarding session is gone.** Steps 1–5 now run under an ordinary authenticated session that holds no community scope | Under OAuth the founder is authenticated from step 0 by construction, so a bespoke onboarding credential has nothing left to do. A membership-less session is already safe: RLS grants it nothing until a membership exists. One fewer concept. — `DERIVED` |
| **Step 5 reframed as review-and-create**; the existing screen and its route are marked for replacement | It was only ever the submit trigger; the credential it collected is redundant once the user is authenticated at step 0. Listed as frontend work in §10 rather than silently dropped, so nobody wonders why a field stopped arriving. — `DERIVED` |
| **Email split into two meanings** — the provider's verified email is the identity and comes from the token; the step-4 field becomes a contact address, renamed `contactEmail` in the payload | Conflating them would let a client change its own identity by typing in a form field. The previously-recorded `auth.users.email` uniqueness trap **inverts**: under OAuth that uniqueness is the identity guarantee rather than a hazard, and the entry is rewritten accordingly. — `AUDIT` |
| **Idempotency rebound** from the onboarding session id to the authenticated account id | The former no longer exists, and the latter is a better key anyway: it coincides with the one-account-one-association rule, so a retry is a natural conflict rather than a silent duplicate. — `DERIVED` |
| **New open item: `profiles.phone_e164` must become nullable** (and `community_registration_requests.applicant_phone_e164` with it) | An OAuth account may have no phone at all. Flagged as a **required schema change before phase 1** — this is the one place the ruling breaks an existing `not null`, and it would otherwise surface as a failed insert on the very first registration. — `AUDIT` |
| **New open items**: which provider(s), and identity-linking policy when the same person arrives via a second provider with the same verified email | Retrofitting a link across existing memberships is painful; the policy is cheap to set now and expensive to set later. — `AUDIT` |
| **New open item**: the non-admin login story under OAuth | Out of scope for an admin-only document, but the same entry path will serve every role, and not every role is equally likely to have a provider account on a personal device. Recorded so it is not discovered late. — `AUDIT` |
| Every reference to the retired mechanism removed from the design sections; it survives only in §10 as work to be undone | Per the ruling, it is not part of the design. It is named once where a screen must physically change, because a removal that is not written down does not happen. — `PO` |

### Not yet propagated

`BACKEND_PLAN.md` §6 and the ERD still describe phone-based authentication end to end — §6.1–6.5,
`otp_challenges`, the SMS-cost reasoning, the rate-limit design keyed on phone, and the
`not null` on `profiles.phone_e164`. **None of it has been rewritten yet**; only the admin
registration document reflects the ruling. Propagating it is a separate pass, deliberately not begun
here, so the change is reviewed before it spreads across four artifacts. — `PO`

The `AuthenticationProvider` port (§6.8) needs **no change** and is worth noting as a deliberate
zero: its `VerifiedIdentity` was defined to carry credential-holder and nothing else — no role, no
membership, no community — which describes an OAuth identity exactly as well as it described a
verified phone. The port stays; only the adapter behind it changes. This is the seam paying for
itself.

---

## 2026-07-29 — Session 4: auditing the founding-admin registration flow

Scope of this pass: read the association-registration / founding-admin onboarding flow in
`frontend/src/` end to end (steps 1–5, success screen, hand-off to `/admin`), compare it against
`frontend-documentation.md`, the ERD, both `.puml` files and `design-of-components.md`, and record
the conflicts. **No conflict was resolved in this pass** — the resolutions are product-owner
decisions and are listed as open in the findings below. Only one factual correction was applied.

### `docs/BACKEND_PLAN.md` and `docs/erd/homebandhu.dbml` — one correction

| Change | Why |
|---|---|
| **"nine feature modules" → "ten"** in `BACKEND_PLAN.md` §4.1(7) and §4.3, and in the `community_settings` comment + Note in `homebandhu.dbml`; both now list the ten ids verbatim | `frontend/src/data/onboardingModules.js` defines **ten** modules, not nine — I miscounted in session 2 and the error propagated to three places. Left uncorrected it becomes a wrong server-side CHECK that silently rejects a module the UI can select. The Note now enumerates the ids rather than pointing at a file, so the count cannot drift again. Also recorded that the frontend doc's example vocabulary (`visitors`, `complaints`, `amenities`, `payments`) exists nowhere in the code and that the code's kebab-case ids win, per the §4.5 principle that vocabulary is the frontend's to own. — `AUDIT` |

### `docs/ADMIN_REGISTRATION_FLOW.md` — **new file**

| Change | Why |
|---|---|
| **New document**: the founding-admin / community registration flow as *implemented*, step by step — every field with its type, whether it is required and what actually validates it; the single API seam; the `POST /communities/register` request and response contract; field-to-table mapping; and the source-file index | The backend team is about to build against this flow and the only existing description of it is `frontend-documentation.md`, which was written ahead of the code and disagrees with it in several places (module vocabulary, coordinate units, the upload seam, E.164 phones). A document that describes **the code** rather than the intent is what makes the endpoint implementable without reading five React pages first. Marked as derived-from-code, with the disagreements called out where they matter. — `DERIVED` |
| The document restates the eight open items from the registration audit in its §9 rather than resolving them | They remain the product owner's decisions and are explicitly tabled while the frontend and backend teammates work. Listing them in the shared document stops someone implementing around them by accident, without pre-empting the ruling. — `PO` (tabled 2026-07-29) |

### Findings recorded but **not** acted on

The registration audit surfaced conflicts that each need a ruling before they can be written into any
artifact. They are held in the session transcript rather than committed to `BACKEND_PLAN.md`, because
writing a resolution into the plan before it is decided is how the plan stops being trustworthy. The
headline items: no postal address is collected anywhere although the ERD and class diagram both mark
it required; map markers are image percentages rather than latitude/longitude; and no flat inventory
exists for apartment communities, so the founding admin's own residency has no `unit` to point at.

### Deliberate zeros

- `docs/class-diagram/*.puml` — read for this audit, **no change needed**. `Community`, `Building`,
  `Unit`, `UnitResidency` and `CommitteePosition` already carry everything the flow produces; the
  conflicts found are about what the *frontend never collects*, not about missing model elements.
- `docs/design-of-components.md` — read, **no change needed**. Its §2 already describes the flow
  accurately, including the note added in session 3 that the founder is verified before onboarding
  begins.
- `frontend/` — **untouched**, as in every prior session.

---

## 2026-07-28 — Session 3: resolving the audited conflicts

Constraints given for this pass: **zero conflicts with the frontend**, and **minimal edits** to the
ERD, class diagram and component design.

### Governing principle adopted

> Resolve a conflict in the layer that owns the truth, and adapt at the boundary.

Identity, cardinality and authorization are the backend's to own, so the *diagrams* changed to match
the backend. Vocabulary, screen count and route paths are the frontend's to own, so the *API* changed
to match the frontend. Nothing was resolved by asking the other side to move. This is what let the
frontend absorb the entire conflict set without a single edit. — `DERIVED`, recorded in
`BACKEND_PLAN.md` §4.5.

### `frontend/` — **no changes, by agreement**

Nothing under `frontend/` has been created, edited or deleted in any session of this work. The
product owner talks to the frontend team before any frontend code moves. Observations about the UI
live in `BACKEND_PLAN.md` §6.9 as questions, never as instructions. — `PO`

### `docs/BACKEND_PLAN.md`

| Change | Why |
|---|---|
| **New §6.1 "The portal is a hint, never a claim"** — the role-prefixed URLs `/auth/{admin,community}/otp/*` survive as thin aliases onto one handler; the prefix is logged as `entry_point` and never read by an authorization decision | "One door" had been conflated with "one screen". Only the *trust* model has to collapse, and the client never held that. Keeping the aliases means the two-portal UI needs no change at all, which is what makes zero-frontend-conflict reachable. — `DERIVED` from the one-door ruling |
| **New §6.6 "The display-role projection"** — the API emits `displayRole` in the frontend's existing 4-string vocabulary alongside the internal `role`/`rank`/`departmentKinds` triple | Exposing the three-axis model as the thing the router switches on would force a rewrite of `getDashboardRouteForRole`, every `requiredRole` array and every `role === 'Admin'` comparison. The projection is computed server-side, so 5 of 6 routing cases work through the existing helper unedited. `displayRole` is **computed, not stored** — adding a shell later stays an API change, not a migration. — `DERIVED` |
| **§6.9 rewritten** from "six things to discuss" into a **compatibility contract (C1–C4)** plus three items that cannot be absorbed | Three of the six were closed outright by C1–C3. The remaining three are additive (a missing staff shell, per-tab sessions, the redundant step-5 OTP), not disagreements. C4 (`redirectTo` optional everywhere) exists so every implied frontend edit is backward-compatible with the current mocks and can be taken independently — a contract rather than a cutover. — `DERIVED` |
| **New §6.10** heading introduced | Content about session claims, permissions and the three membership-creating flows had been sitting *inside* §6.9, under a heading that said "not changes, questions". It was neither. Structural fix. — `AUDIT` |
| **New §4.5 Resolution register** | A per-conflict record of how each §4.2.1 / §4.4 finding was closed and which artifact absorbed it, so the audit and its resolution are readable side by side. — `DERIVED` |
| §10.9, §10.12, §10.13 struck through as resolved | Superseded by product-owner rulings. §10.13 in particular recommended *one* staff assignment per person; that is now overruled by the rank-dependent cardinality rule, and the entry records that the old recommendation rested on a scalar `department_id` assumption which no longer holds. — `PO` |
| §10.11 `department_kind` list aligned to the ERD's five values | `.puml` and `.dbml` had drifted apart during editing. Trades (plumbing, electrical) are `job_title` and `skills`; a *kind* exists only where a dashboard differs. — `AUDIT` |

### `docs/class-diagram/homebandhu-domain.puml` — 13 edits, no package moved, no association deleted

| Change | Why |
|---|---|
| `AuthUser` gains `phone {unique}` + `phoneConfirmedAt`; `email` demoted to `[0..1]`; note names phone as *the* login identifier | The identity class had no phone attribute at all, while phone is the only login identifier. The diagram asserted an email-first model that no screen implements. — `AUDIT` |
| `ResidentInvite` gains `recipientPhoneE164 {required}`, `tokenDigest {unique}`, `codeDigest`, `attemptCount`; `recipientEmail` → `[0..1]`; `accept(p)` → `redeem(secret, v)`; note states the two factors | Same email assumption. The class also had *no digest fields* despite its own note promising that only digests are stored. `redeem` now takes both factors in its signature so the mandatory-token rule is visible in the model, not just in prose. — `AUDIT` + `PO` |
| `CommunityMembership` scope note rewritten: one active membership per profile, no per-role exceptions; multi-department moved to `StaffAssignment`; `{role vs capability}` clause added | The old note said residents and admins get one membership but staff get many — contradicting the one-association rule — and put multi-*department*-ness on the membership. Its "staff & non-staff not mixed" clause also forbade the security supervisor who lives in Flat 302, a real case. — `PO` |
| `Profile.activeMemberships() : List<>` + `membershipIn(c)` → `activeMembership() : Optional<>` | Both signatures presumed multi-community. The invariant is now enforced by the return type rather than by a note someone has to read. — `DERIVED` |
| `Profile.verifyPhone(otp)` → `markPhoneVerified(v)`; `CommunityRegistrationRequest.verifyOtp(code)` → `attachVerifiedIdentity(v)` | Two aggregates were independently verifying OTPs. The `AuthenticationProvider` seam requires exactly one verifier; neither aggregate should know what an OTP is. — `PO` |
| `AdminMembership.inviteResident(u, email)` → `(u, phone)`; `grantRole(p, r)` → `assignStaff(p, d, rank) : StaffAssignment` | Invites are phone-based. Granting staff-ness creates a row with a department and a rank; it is not a value set on an enum. — `AUDIT` |
| `applicantEmail {required}` → `[0..1]` on `CommunityRegistrationRequest` and `AccessRequest`, phone promoted | Both intake paths collect a phone in the UI. — `AUDIT` |
| `MembershipRole` 5 values → `RESIDENT, STAFF, ADMIN`; `WorkerMembership`/`SecurityMembership`/`ManagerMembership` merged into `StaffMembership` with a guard note | The flat 5-value enum cannot express a security *supervisor* or a committee member. Required for consistency with the ERD, which already made this change. The guard note records that visitor operations need `department.kind = SECURITY` and work-order operations need rank ≥ SUPERVISOR — neither is implied by `role = STAFF`. — `PO` |
| New enums `StaffRank`, `DepartmentKind`, `CommitteePositionStatus` | The other two axes had no representation in the diagram. — `PO` |
| `StaffAssignment` gains `rank`, `shift`; its invariant note replaced with the rank-dependent cardinality and the array-claim consequence | The old note said "one active staff assignment per membership", which the product owner's rule invalidates: one manager per department, managers/supervisors single-department, workers multi-department. This is also *why* the JWT carries `department_ids` as an array. — `PO` |
| `CommunityMembership "1" -- "0..1" StaffAssignment` → `"0..*"` | Direct consequence of the line above; the old multiplicity had become wrong. — `DERIVED` |
| `Department` gains `kind`, contacts, hours, `slaHours`, `head()`; note added | `kind` selects the staff shell and is the only axis load-bearing in RLS. The other fields are required by `design-of-components.md` §3 and already exist in the prototype's seed data. — `AUDIT` |
| New `CommitteePosition` class + two associations | Committee members are residents with extra views, and the admin is a committee member and therefore also a resident. Unrepresentable before. — `PO` |
| New `VerifiedIdentity` value object with its rule in a note | It existed only in prose. The note carries the load-bearing constraint: it holds phone + auth-user-id and **no role, membership or community**, which is what keeps the OTP mechanism swappable. — `PO` |

### `docs/class-diagram/homebandhu-architecture.puml`

| Change | Why |
|---|---|
| New `AuthenticationProvider` `<<port>>` interface with the CI import-linter rule in its note | The seam was a plan decision with no representation in any diagram. Placed on the architecture diagram rather than the domain one because it is infrastructure, not domain. — `PO` |
| New `MembershipResolver` service with `displayRole`/`dashboard` | Makes the authentication/authorization split visible: `AuthService` composes two collaborators that know nothing of each other. — `DERIVED` |
| `AuthService ..> SupabaseAuth` re-pointed to `AuthenticationProvider ..> SupabaseAuth` | The old edge drew the exact dependency the seam forbids. — `DERIVED` |
| `AuthService.requestLoginOtp` gains `entryPoint`; `verifyLoginOtp` takes `challengeId` not `phone` | Reflects the portal-as-hint rule and the challenge-based verify contract. — `DERIVED` |

### `docs/class-diagram/README.md`

Model notes rewritten: 5-subclass → 3-subclass, the three-axis role model, role-selects-shell-only,
one-membership-per-profile, and phone-as-identifier. — Reason: the README stated the old flat enum as
fact and would have been the first thing a reader trusted. `AUDIT`

### `docs/design-of-components.md` — 3 sentence-level edits, no restructuring

The document describes the prototype accurately, so it was **corrected, not rewritten**. Rewriting it
to describe a future state would have made it wrong about the thing it exists to describe.

| Change | Why |
|---|---|
| "separate entry and login *flows*" → separate *entry points* served by a single flow, with the explicit clause that the entry point is never a claim about role | This bullet was the document-level source of the two-portal split and of the four role-prefixed endpoints. — `PO` |
| Invitation bullet now states the secret is *required* for activation, not a shortcut | The mandatory-token rule. The document's own §3 language about time-limited single-use invitations already supported this. — `PO` |
| Per-tab session bullet marked as prototype behaviour, with the server-session consequence named | True today via `sessionStorage`; impossible once sessions are cookies, which are per-origin. Left as a described limitation rather than deleted, because it is still what the prototype does. — `DERIVED` |
| Onboarding OTP bullet notes the reordering | The founder is verified before onboarding begins, so the confirmation gates entry rather than closing the flow. — `DERIVED` |

### Rendered diagrams

`HomeBandhu-Domain-Model.{svg,png}` and `HomeBandhu-Architecture-Layers.{svg,png}` regenerated from
source with PlantUML 1.2024.7 (`-charset UTF-8`).

The PNGs were re-rendered a second time with `-DPLANTUML_LIMIT_SIZE=20000`. First attempt silently
clipped both at PlantUML's 4096 px default — the domain diagram is 16703 px wide, so roughly
three-quarters of it was missing with no error raised. Worth remembering: **PlantUML crops instead of
failing.** Check that the PNG's dimensions match the SVG's `viewBox` before trusting it.

Reproduce with:

```bash
java -Djava.awt.headless=true -DPLANTUML_LIMIT_SIZE=20000 -jar plantuml.jar -charset UTF-8 -tsvg -tpng docs/class-diagram/*.puml
```

### `docs/erd/homebandhu.dbml` — **no changes needed this session**

v2 already carried every column and constraint the resolutions depend on: `staff_rank`,
`department_kind`, the three partial uniques on `staff_assignments`,
`one_active_membership_per_profile_uq`, and the invite digests. Recorded here as a deliberate
zero — the ERD was checked, not skipped.

---

## 2026-07-28 — Session 2: the auth model

Full reasoning in `BACKEND_PLAN.md` §6; product-owner rulings summarised here.

| Decision | Why | Source |
|---|---|---|
| **Phone (E.164) is the only login identifier**; email is optional profile data | Every implemented screen collects a phone. The class diagram and ERD had assumed email magic links. | `PO` |
| **No login button, no signup button** — one phone field, one endpoint pair; the backend decides login vs. activation vs. found-a-community | The client must never assert a privileged role before authenticating, which `frontend-documentation.md` line 21 requires and its own line 279 endpoint list contradicts. Resolved toward line 21. | `PO` |
| **The request step discloses nothing** — identical `202` for every valid phone, SMS sent to unknown numbers too | Closes the account-enumeration oracle, at the cost of SMS to non-users. The alternative (reveal before OTP) was recommended for cost and **overruled**. Knock-on: the founder is verified at step 0, making the step-5 onboarding OTP redundant. | `PO`, overruling a recommendation |
| **Rate limiting keys only on server-side facts** — phone, IP, /24, global circuit-breaker, as queries over `otp_challenges`; no Redis in v1 | A client-supplied token is an evasion tool, not a control: the attacker clears it or mints a fresh one. The frontend holds nothing usable anyway — `lib/ids.js#genId` is `Date.now()` + `Math.random()`. Distinct from the trusted-device cookie, which is legitimate but serves SMS cost, not rate limiting. | `DERIVED`, answering a direct question |
| **One phone = one association**, enforced by a partial unique on `(profile_id) WHERE status='active'` | People live in one home. Deletes `409 MEMBERSHIP_SELECTION_REQUIRED`, the `membershipId` verify field and the selection token from v1. | `PO` |
| **Roles with no dashboard still log in**, landing on a WIP placeholder | An admin must not be able to provision a staff member who then cannot sign in at all. `409 UNSUPPORTED_ROLE` retired. Blocking them was recommended and **overruled**. | `PO`, overruling a recommendation |
| **The invite token is mandatory — it is deliberately a second factor** | OTP proves the phone; the token proves the invitation. An earlier draft proposed auto-redeeming a pending invite on OTP alone, treating the token as a deep-link convenience; **overruled**. Verifying a phone with a pending invite yields an *activation ticket, not a session*. Contains admin typos: the stranger who receives a misdirected SMS still cannot activate. | `PO`, overruling a draft decision |
| **Rank fixes assignment cardinality** — one manager per department; managers/supervisors single-department; workers multi-department | Supplied as a domain fact. It invalidated a flat "one active staff assignment per membership" constraint already written into the ERD, and forced `department_ids` in the JWT to be an **array** rather than a scalar. | `PO` |
| **All authentication behind one `AuthenticationProvider`**; nothing else may import `supabase.auth` or reach an SMS vendor | Cheap SMS is unresolved, so the mechanism must not be load-bearing. `VerifiedIdentity` carries phone + auth-user-id only — no role, membership or community — because authentication must stay separable from authorization. Three implementations selected by `AUTH_PROVIDER`; a CI import-linter rule fails the build if the boundary is crossed. | `PO` |

### Artifacts touched in session 2

- `docs/erd/homebandhu.dbml` — `community_memberships` unique moved to `(profile_id) WHERE
  status='active'`; `staff_assignments` gained the three rank-dependent partial uniques;
  `otp_challenges` gained `channel`, `resend_count`, `user_agent` and two rate-limit indexes; new
  `trusted_devices` table. *Why:* each is the physical enforcement of a ruling above — the rules live
  in Postgres, not in application convention.
- `docs/BACKEND_PLAN.md` — §6 rewritten end to end (6.1–6.9); §3.1 gained three `DECIDED` blocks;
  new §3.10, §4.2.1, §4.4.

---

## 2026-07-28 — Session 1: the role model and the ERD

| Decision | Why | Source |
|---|---|---|
| **Roles are three orthogonal axes**, not one enum: `role` × `department.kind` × `rank` | The flat 5-value `MembershipRole` cannot represent a security supervisor or a committee member. | `PO` |
| **Committee members are residents with extra views**; the admin is a committee member and therefore also a resident | `register_community` must create the ADMIN membership *plus* a `unit_residency` *plus* a `committee_position`, in one transaction — so the statement is true in the data rather than in application logic. | `PO` |
| **Community type is exclusive and immutable** — apartment **xor** standalone homes | Nothing in the schema prevented a mixed community. | `PO` |
| **New associations are approved immediately**; the operator-approval gate is deferred | Out of scope for every phase. The review columns stay so the gate can be switched on later without a migration. | `PO` |

### `docs/erd/homebandhu.dbml` — v1 → v2

48 tables → **63**. v1 preserved verbatim as `homebandhu-v1-milestone1.dbml` so the two are diffable;
every change in v2 is tagged `CHANGED:` or `NEW:` in a comment or Note.

15 tables added: `activity_events`, `amenity_blocked_slots`, `amenity_images`, `auth_sessions`,
`committee_positions`, `community_settings`, `complaint_attachments`, `complaint_categories`,
`complaint_comments`, `complaint_read_state`, `emergency_contacts`, `idempotency_records`,
`otp_challenges`, `security_incidents`, `trusted_devices`. *Why:* every one is required by a screen
that already exists in the prototype or by a rule in `design-of-components.md`; the full
justification is `BACKEND_PLAN.md` §4.3 C.

Corrections in v2 worth calling out, because each fixes something that would have broken a real
workflow rather than merely being untidy (`BACKEND_PLAN.md` §4.3 A):

- `units` unique key `(community_id, unit_label)` → `(community_id, building_id, unit_label)`. Flat
  101 exists in Block A *and* Block B; the second block's units would have failed to insert.
- `resident_invites` and `access_requests` moved from email-required to phone-required.
- `communities.active_admin_membership_id` made deferrable — it is a genuine FK cycle, and without
  deferral `register_community` cannot be written as one transaction.
- `community_id` denormalised onto ten event/child tables, with composite FKs so it cannot drift.
  Without it every RLS policy on those tables joins to the parent on every row of every query — the
  single biggest performance risk in the design.
- `version` column + `bump_version()` trigger on every editable table, because
  `frontend-documentation.md` mandates `If-Match` and a `STALE_VERSION` error with nothing to compare
  against.

*Note:* the ERD image in `docs/erd/` is still rendered from v1 and needs regenerating on
dbdiagram.io. The `.dbml` is the source of truth.
