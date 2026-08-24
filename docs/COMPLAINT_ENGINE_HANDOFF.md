# Handoff to the complaint management engine

**Written:** 2026-08-10, from the `services-and-security` branch.
**For:** whoever owns the complaint lifecycle.
**Why this file exists:** building the service-operations surface — hiring,
dispatch, work orders, the worker portal — produced a set of questions that
**cannot be answered from inside it**. Each one is about what a *complaint* means
or when it ends, so each one belongs to you rather than to us. Rather than guess
quietly and leave you to discover the guess later, we took a default, wrote down
what it costs, and put it here.

**Nothing in this file is a request.** Every item below has a working default in
the branch today. If you change none of them the system is coherent. What we are
handing over is the *reasoning*, so that when you do change one you know what it
was holding up.

**If you are new to the complaints engine, read
[`COMPLAINT_ENGINE_STATE.md`](COMPLAINT_ENGINE_STATE.md) first** — it is the
orientation document (what exists, the workflow, every endpoint and screen, and
the consolidated worklist). This file is the argument behind each open question.

---

## Reconciliation note — 2026-08-23

The useful fixes from `complaint-engine-v2` are now represented by the single
forward-only migration
`backend/supabase/migrations/20260823120000_complaint_engine_v2_repairs.sql`.
The branch's two `2026081714…` migrations are not part of the current chain:
their timestamps precede a migration already recorded by the hosted project,
and one copied an older notification route over the corrected `/worker?job=`
route on `main`.

The reconciliation fixes four concrete database defects without changing the
HTTP API:

1. `sync_dispatch_tasks` casts its manual-window queue priority to the
   `smallint` accepted by `enqueue_dispatch_task`.
2. `project_complaint_from_jobs` resolves `complaint_id` according to the
   triggering table, instead of reading a field that does not exist on
   `work_order_assignments`.
3. Dispatch ranking has a private, explicit `include declined` mode. Normal
   dispatch remains strict; the supervisor's `include excluded` view can now
   actually show a declined worker and label that worker excluded.
4. Critical force assignment calls the internal ranking directly, so a worker
   decline transaction no longer fails the supervisor-only candidate check.
   Availability, departure, overlap, and skill checks still apply.

There is intentionally no server-side candidate cache. Eligibility changes
with declines, unavailability, departures, and accepted assignments. The
frontend's existing React Query mutation invalidation already refreshes the
`work-orders` candidate queries, and the migration reloads PostgREST's schema
cache because it adds a function overload.

---

## 0. The one fact that frames all seven

**The service-operations feature never writes `complaints.status`. Not once.**

Verified by reading rather than asserted: across
`0036_work_orders.sql`, `0037_dispatch_engine.sql` and `0039_worker_actions.sql`
— every table write in the dispatch chain — the `complaints` table appears only
as `select * into v_complaint` and as a foreign key. There is no
`update public.complaints` statement in any of the three.

So there are **two state machines over one complaint**, and they are not coupled:

| | Values | Written by |
|---|---|---|
| `complaints.status` | `open · acknowledged · in_progress · resolved · closed · cancelled` (`0001`:14, a real Postgres ENUM) | `raise_complaint`, `update_complaint`, `reopen_complaint`, `confirm_complaint_resolution` — all yours |
| `work_orders.status` | `draft · awaiting_resident · offered · scheduled · in_progress · completed · failed · cancelled` (`0036` §1, `text` + CHECK) | the supervisor's triage RPCs, the dispatcher, and the worker's five verbs |

A complaint can therefore sit at `open` while a technician is standing in the
resident's kitchen with the job at `in_progress`, and the resident's complaint
list will say *Pending*.

**That is deliberate, and it is the decision we most want you to overturn
knowingly rather than inherit.** The reasoning for leaving it uncoupled was that
a work order is *a* response to a complaint and not *the* complaint — D5 in
[`plans/SERVICE_OPERATIONS_PLAN.md`](plans/SERVICE_OPERATIONS_PLAN.md) makes one
complaint able to carry many work orders, because a failed visit is rescheduled
as a second job and a reopened complaint goes to a different supervisor. Once
that is true, "the complaint's status" is not a projection of any one job's
status, and picking a job to project from is a rule nobody had written down.

The resident is not left in the dark in the meantime: **the timeline carries the
whole story** (§3), which is why this was survivable as a default rather than
shipping-blocking. But a resident who reads a status badge and not a timeline
sees nothing move for two days.

**If you want them coupled**, the cheapest correct shape is a trigger on
`work_orders` — `after update of status` — that moves the complaint forward but
never backward, because the complaint has exits (`resolved`, `closed`,
`cancelled`) that a job knows nothing about. That is the same mechanism `0037`
already uses to keep `dispatch_tasks` in step with `work_orders`, so there is a
worked example one file over.

---

## 1. Completing the job does not resolve the complaint

**What happens today.** `complete_work_order` (`0039` §3) closes the assignment,
sets the work order to `completed`, and writes a `job_completed` event on the
complaint timeline. The complaint's own status is untouched. The function says so
in its own comment:

> 'The work is done. Closes the assignment and the job — and deliberately not
> the complaint, which is the resident's to confirm.'

**Why we stopped there.** A resident whose tap still drips has a complaint that
is not resolved, whatever the worker pressed. Letting the person who did the work
declare the work satisfactory is exactly the accountability gap **US-2.8** is
about. And the resident already has the endpoint for it —
`POST /complaints/{id}/resolution` → `confirm_complaint_resolution` (`0031`:522)
— which is the *resident's* act and requires a 1–5 rating.

**The gap this leaves you.** `confirm_complaint_resolution` refuses anything that
is not already `resolved` (`0031`:546). So after a completed visit, the complaint
sits at whatever it was, and **nobody has moved it to `resolved`** — meaning the
resident cannot confirm even if they want to. The path from *work done* to
*complaint closed* has a missing first step, and that step is a management act,
not a worker's one.

The three shapes, with what each costs:

| Option | Cost |
|---|---|
| The supervisor marks it `resolved` by hand (today's implied path, via `PATCH /complaints/{id}`) | Works now, needs nobody. Depends on a human remembering; the complaint stays open when they don't |
| `complete_work_order` also sets `resolved` | One line. Hands the resolution claim to the worker — the thing we declined to do |
| A `job_completed` trigger sets `resolved` **only when no other live work order exists on the complaint** | Correct under D5's many-jobs rule, and the check is the one `dispatch_failed_visit_escalation` already performs (`0037`) |

We think the third, but it is a policy about who may claim a fix, so it is yours.

---

## 2. Auto-resolution after 24 hours of resident silence

**This is the biggest one, and it is already written down twice as an open
question** — `plans/SERVICE_OPERATIONS_PLAN.md` risk 3, and
[`design/SERVICE_OPERATIONS_DESIGN.md`](design/SERVICE_OPERATIONS_DESIGN.md) §4.4
and §5.

The product document specifies that a complaint sitting 24 hours with no resident
response auto-resolves. **We did not implement that.** What
`dispatch_resident_timeout` (`0037`) does instead is *proceed with the proposed
visit* and notify the resident that it is going ahead —
`awaiting_resident` → `offered`.

**The reasoning, because it is the part worth arguing with.** The two acts differ
in who they cost. Proceeding needs no product decision: it is exactly what the
resident was told would happen when the slot was proposed. Closing a complaint the
resident may never have seen is a decision about accountability — the subject of
US-2.8 — and 2 a.m. in a background job is the wrong place to make one quietly.

**What we are not claiming.** We are not claiming the product document is wrong.
We are claiming that the sentence *"auto-resolve after 24 hours"* answers a
different question from the one the dispatcher was in a position to ask, and that
if it is going to be implemented it should be implemented **by the complaint
engine, against the complaint's own clock**, not as a side effect of a scheduling
timer that happens to be running.

Concretely, the two clocks are different and this is easy to miss:

- `dispatch_tasks.due_at` for a `resident_timeout` is 24 h after **a visit was
  proposed**. It exists only for complaints that reached triage.
- `complaints.expected_resolution_at` is set at raise time from
  `complaint_sla_hours(priority)` — 24/48/72 h by priority (`0031`:123) — and is
  the clock `is_overdue` reads. It exists for **every** complaint.

A complaint nobody ever triaged has the second clock and not the first, and it is
precisely the complaint an auto-resolution rule would be most dangerous on.
Auto-resolving off the dispatcher's timer would therefore close the complaints
that *did* get attention and leave the neglected ones open forever — the exact
inversion of the intent.

**If you build it**, `reopen_complaint` (`0031`:429) is the safety net that makes
it defensible: the raiser can reopen from `resolved` or `closed`, it restarts the
SLA and it clears the rating. An auto-close with a visible, one-tap reopen is a
different proposition from an auto-close without one. It is already built.

---

## 3. The timeline vocabulary is a shared namespace with no lock on it

`complaint_events.event_type` is **`text` with no CHECK constraint** (`0001`:70).
That was a gift while building — the eight new event types this feature writes
needed no migration at all — and it is a hazard for you, because there is nothing
in the database stopping two workstreams from spending the same word on two
different meanings.

Everything currently written, and by whom:

| Event type | Written by | Renders as |
|---|---|---|
| `raised`, `status_changed`, `assigned`, `progress_changed`, `due_date_changed`, `note_added`, `comment_added`, `reopened`, `resolution_confirmed` | `0020`, `0031` — **yours** | the nine that predate this feature |
| `job_created`, `job_scheduled`, `job_declined`, `job_assigned`, `job_cancelled` | `0036` | "Work raised", "Visit scheduled", … |
| `job_started`, `job_completed`, `job_failed` | `0039` | "Work started", "Work completed", "Visit unsuccessful" |

**One near-collision is worth knowing about, because it shaped a decision.**
`job_declined` means **the resident declined the proposed time** — it is written
by the resident's own scheduling route and renders as *"You declined the proposed
time."* When Step 6 built the worker's *decline this offer* action, reusing that
word would have put a sentence on the resident's timeline blaming them for a
worker's refusal. So **a worker declining an offer writes no timeline event at
all**, which is a small honest gap rather than a wrong sentence.

Two consequences for you:

- If you ever want the resident to see *"we asked three technicians and none were
  free"*, that needs a **new** event type; do not reach for `job_declined`.
- There is deliberately **no `job_accepted`**. A worker taking an offer writes
  `job_assigned`, because from the resident's side it is the same fact — somebody
  is now coming, and this is their name.

The renderer is `_EVENT_LABELS` and `_event_message` in
[`resident_complaints_service.py`](../backend/app/services/resident_complaints_service.py):55-147.
An unknown type renders as the raw type rather than vanishing, on purpose: a
timeline that silently omits a row hides its own bug.

**`_is_internal_comment_event` is the one piece of that file to read before
touching it.** `0020` writes a `comment_added` event for internal comments too,
and the RLS policy on `complaint_events` scopes by complaint rather than by
comment visibility — so the shadow of an internal comment does reach the
resident's timeline and is stripped in Python, not in SQL. If you move that
filter into a policy, delete the Python; two filters is one too many.

---

## 4. A failed visit escalates to a human and stops

`report_work_order_failure` (`0039` §3) sets the job to `failed`, increments
`failed_attempt_count`, and requires a reason — *"could not be done"* with no
reason guarantees a second wasted visit, because nobody downstream can tell
*nobody was home* from *the part is out of stock*.

Two hours later `dispatch_failed_visit_escalation` (`0037`) notifies the
department's manager, falling back to the community's admins if the department has
no manager on its roster. **It does not raise a replacement job, and it does not
touch the complaint.**

**The idempotency check in that function is the piece most likely to be
misread**, so it is worth restating here: every other firing function in `0037`
checks a status, and this one cannot. A failed job stays `failed` forever — the
answer to a failed visit is a *new* work order (D5), not a revived old one — so a
status check would re-escalate on every redelivery. It asks instead whether a
**newer work order exists on the same complaint**, and separately whether the
complaint has been settled some other way, because escalating a visit for a
complaint nobody has any more is the false alarm that teaches people to ignore the
real ones.

**That second check is where this touches you.** It reads
`complaints.status in ('resolved','closed','cancelled')`. If the complaint engine
grows a state that means *settled* under another name, this function will keep
escalating visits for complaints that are over. It is one `in` list in one
function, and it is the only place in the dispatch engine that depends on the
meaning of a complaint status rather than on its existence.

**What is not built and is arguably yours:** the product document says a reopened
complaint goes to a *different* supervisor. Nothing implements that. Reopening is
`reopen_complaint`, which is yours, and "a different supervisor" is a routing rule
about complaints rather than about jobs.

---

## 5. Priority is inherited once and never re-inherited

`0031`'s header argued that the schema should not carry two *names* for one
concept and settled on `priority`, citing `work_orders.priority` as the admin's
existing column for the same idea. It did not check what that column allowed:
`complaints.priority` was `low | medium | high` and `work_orders.priority`
defaulted to `'normal'` with **no CHECK at all**. The two columns cited as the
same idea agreed on the name and disagreed on every value.

Corrected in `0036` §1 — same three words, default `'medium'` — and
`create_work_order` **inherits the complaint's priority** rather than accepting
one as a parameter. A job's urgency *is* the complaint's urgency, and a parameter
would be a second copy to keep in step.

**The open edge:** inheritance happens once, at creation. A supervisor who raises
a complaint's priority afterwards does not re-prioritise a job already scheduled
from it, and `high` priority is not cosmetic — it is what makes the dispatcher
skip the offer round and auto-assign immediately (`0037`'s trigger table). If
escalating a complaint should escalate its live jobs, that is a rule about
complaints and belongs on your side of the line. `update_work_order` accepts a
`p_priority` today, so the lever exists; nothing pulls it automatically.

---

## 6. Two defects we fixed under your surface, so you do not re-fix them

Found while building on top of the complaint path, both fixed in this branch
(recorded in
[`plans/SERVICE_OPERATIONS_PROGRESS.md`](plans/SERVICE_OPERATIONS_PROGRESS.md)
§5.8 and §8):

- **`complaints_service.py` called a repository function that did not exist.**
  `people_repo.get_membership_id_for_profile(...)` appeared exactly once in the
  codebase — at the call site. Both admin complaint writes raised `AttributeError`
  → 500 on the first line they reached. `tests/api/test_complaints.py`
  monkeypatched the whole service, so the suite had never executed the line.
  Fixed by injecting `MembershipContext` at both routes, which removed two
  database reads per write rather than adding a function.
- **`AddCommentRequest.visibility` defaulted to a word the database rejects.**
  The default `"resident"` reached `add_complaint_comment`, which coalesces only
  blanks, so it survived to the insert and violated
  `complaint_comments_visibility_check` — `visibility in ('public','internal')`
  (`0020`:101). Every comment posted through that endpoint failed with a 422,
  including the frontend's, which hardcodes the same word. Fixed by
  `comment_visibility_to_storage` in `app/domain/vocabularies.py`: **`resident`
  is still what the frontend sends and what `API.md` documents**, and `public` is
  now also accepted, so a client that has learnt the stored word is not forced
  back through the display word.

The second is the pattern to expect more of: the frontend, `API.md`, the Pydantic
model and the test all said one word, and the database and both RPCs said another.
`app/domain/vocabularies.py` is where that seam lives now — if you add a complaint
status, a visibility or a priority, add it there rather than in a service.

---

## 7. What to read, in order

| Document | For |
|---|---|
| [`plans/SERVICE_OPERATIONS_PLAN.md`](plans/SERVICE_OPERATIONS_PLAN.md) | D5 (many jobs per complaint) and D6 (`complaint_events` is the audit trail). The two decisions everything above rests on |
| [`design/SERVICE_OPERATIONS_DESIGN.md`](design/SERVICE_OPERATIONS_DESIGN.md) §4.4, §5 | The auto-resolution default, and the open-questions table it sits in |
| [`plans/SERVICE_OPERATIONS_PROGRESS.md`](plans/SERVICE_OPERATIONS_PROGRESS.md) §4 | Everything the build learned that the plan got wrong. §4.11 is the priority one, §4.17 the dispatch one |
| `backend/supabase/migrations/0031_resident_complaints.sql` | Your own file — the SLA rule, `reopen_complaint`, `confirm_complaint_resolution` |
| `backend/supabase/migrations/0037_dispatch_engine.sql` | The four timers. The only file of ours that reads the *meaning* of a complaint status |

**And one caveat that applies to every claim above.** Per
`backend/supabase/migrations/README.md`, **no migration in this project has ever
been applied to any database** — including `0001_baseline.sql`. Every predicate
described here is unexecuted. What is written down is what the SQL says, checked
by reading and by `pglast`, not what a database has been observed doing.

> **Update 2026-08-12: the caveat above is no longer true.** The entire chain —
> `0001_baseline.sql` through `20260812160000_legacy_status_defaults.sql`,
> including the complaint routing file — is applied to the hosted Supabase
> project and verified with per-file post-checks. The sections above are left
> as written; only this deployment claim changed.

---

## 8. Added 2026-08-11 — the assignment control, and a question that is yours

The admin department screen's "Assign technician" dropdown changed, and one
thing about it is **deliberately left undecided** because it is yours.

### What changed, and why it had to

`DepartmentDetail.jsx` read its roster from `department.staff` — the zustand
snapshot's copy. That list is **always empty**: `GET /dashboard/snapshot` builds
every department as `{ staff: [], categories: [] }`
(`dashboard_service.py`:203). The control looked functional only because the
department form used to collect typed-in staff names and write them
optimistically into the same local array, so it survived until a reload.

Those typed-in names are gone. Technicians are outside people now — they
register, apply or are invited, and a manager decides — so the department form
no longer invents them, and the dropdown had to stop reading a list nothing
fills. It now reads the real roster (`GET /departments?pageSize=100`, whose
`staff[]` is `staff_assignments` including `serviceProviderId` since `0042`),
and is relabelled **"Assign to staff"**, since a hired plumber is not a
technician in any vocabulary this schema uses.

The empty state now links to `/admin/departments/:id/hiring`, which is the
screen that actually populates it.

### The question, unanswered

**`assigneeStaffId` on a complaint is not `work_order_assignments.staff_assignment_id`.**

The screen sets it optimistically in zustand; the backend records assignment on
a *work order*, not on the complaint, and D5 says a complaint may have several.
So there are two ideas of "who is on this" and nothing reconciles them:

| | Where it lives | Who writes it |
|---|---|---|
| `complaint.assigneeStaffId` + `assignee` label | zustand, this screen | an admin using the dropdown |
| `work_order_assignments.staff_assignment_id` | Postgres | `create_work_order`, and the dispatch engine |

Three ways this could go, and **none of them is ours to choose**. *(The two "has no caller"
statements below were true when written and are not now — the triage screen calls both
`POST /complaints/{id}/work-orders` and `POST /work-orders/{id}/assign`, at
`frontend/src/features/workOrders/workOrdersApi.js:61` and `:110`. It calls them about a **work
order**, not about `complaint.assigneeStaffId`, so the fork itself is untouched; see §10.)*

1. **The dropdown creates a work order.** Assignment stops being a complaint
   field; `POST /complaints/{id}/work-orders` already exists and has no caller.
   Truest to D5, and it changes what the control means.
2. **The dropdown assigns the complaint's existing work order.**
   `POST /work-orders/{id}/assign` exists, also with no caller. Needs an answer
   for a complaint with none, or several.
3. **`complaints.assigned_to_membership_id` stays the admin's own field** and
   means "who is accountable", separate from who is doing the work. Then the two
   are not in conflict and both should be shown.

The frontend has been left on the shape it had — an optimistic local field —
because changing it commits to one of these, and the choice belongs to whoever
owns the complaint lifecycle. Nothing new depends on the answer; the control
works either way. But it is a real fork, and it is the one thing on that screen
that is still pretending.

---

## 9. Added 2026-08-12 — a complaint now has a department, and this is not §8

**A ruling was made on complaint routing and it is not the one §8 asks you
about.** Read this section before you conclude that your fork was decided for
you, because it was not.

`20260812090300_complaint_department_routing.sql` gives `complaints` a `department_id` and
fills it when the complaint is raised. The rule, from the product owner on
2026-08-12, in precedence order:

1. the complaint's **category**, matched to `complaint_categories` and followed
   through `department_categories` (`0019`) to a department;
2. failing that, **the department the resident named** on the form — a new
   optional `departmentId` on `POST /complaints`, whose "Not sure" option sends
   `null`;
3. failing that, **nothing** — an admin triage queue, and an admin allots it.

A category attached to several departments routes to *nothing* rather than
picking, so the ambiguity becomes a question a human answers rather than a wrong
answer nobody sees.

### Why this does not decide §8

§8 is about **which person** is working a complaint —
`complaints.assigned_to_membership_id`, `work_order_assignments`, and an
optimistic field on a screen. This is about **which department owns it**. They
are different questions and `complaint_department_routing` deliberately answers only the second:

* nothing here writes `assigned_to_membership_id`;
* nothing here creates or assigns a work order;
* `department_complaints()` reports the complaint and its open transfer request,
  and says nothing about who is doing the work.

If anything, the fork in §8 is now easier to take: a complaint has a department
before any work order exists, so option 2 ("the dropdown assigns the complaint's
existing work order") no longer has to invent a department to create one in.

### What else changed under you, and why

**Four notifications stopped going to every manager in the community.**
`notify_community_staff` means every admin *and every manager*, so the plumbing
department's manager was told about lift complaints — raised, reopened,
resolution-confirmed and commented — each with a link to `/admin/complaints`,
which a manager's portal has no route for. They now go through
`notify_complaint_staff` (`complaint_department_routing`): the community's admins, plus the complaint's
**own** department manager.

**All four are in `complaint_department_routing`, and none of them is in `0031`.** That file is
applied to the hosted project and immutable, so `reopen_complaint`,
`confirm_complaint_resolution` and `add_complaint_comment` are repeated there in
full — whole bodies, to change one call each — with every difference from the
applied text marked `-- CHANGED` in place. `raise_complaint` is dropped by its
exact six-argument signature and rebuilt with seven, because adding a parameter
to a `create or replace` produces a second overload rather than a replacement.

**Read the definitions in `complaint_department_routing`, not `0031`'s.** `0031` cannot carry a
pointer forward saying so, which is the practical cost of the boundary.

### The one thing here that is a judgement call, and is yours

**A supervisor can ask for a complaint to be moved; their manager decides.**
`complaint_department_requests`, and the two RPCs either side of it. The shape
was chosen because a supervisor who could move work out of their own department
could empty it — but *whether a transfer should also notify or need consent from
the receiving department* is a lifecycle question and it is unanswered. Today
the receiving department finds out by being notified after the fact.

## 10. Added 2026-08-12 — the triage screen exists now, and two questions came with it

**§8 addendum — the fork is now cheaper, and still yours.** Work orders have a
screen: `/{portal}/departments/:departmentId/work-orders`, calling all eight
`work_orders.py` operations. It treats a work order as its own resource and
**does not touch `complaint.assigneeStaffId`**; the "Assign to staff" dropdown
on `DepartmentDetail.jsx` is untouched and still an optimistic local field. All
three of §8's options remain open, but options 1 and 2 no longer require
anything to be built — choosing between them is now purely a decision about
what the *complaint's* assignment control means. Which is it: does that
dropdown (1) raise a work order, (2) assign the complaint's existing work
order, or (3) stay a separate "who is accountable" field, shown alongside the
work order's assignee rather than instead of it?

*(§10's two questions are both settled by the 2026-08-12 rulings — see §11.)*

**New — may work be raised against a complaint that has ended?**
`create_work_order` reads the complaint's department, its community and the
slot, and never reads `complaints.status`. A supervisor can therefore raise a
job against a `resolved`, `closed` or `cancelled` complaint, and the triage
screen's "Raise work" tab does not filter those rows out — it lists whatever
`GET /departments/{id}/complaints` returns. The default is deliberate and
defensible (a snag found after closure is real work, and D5 already makes a
reopened complaint carry a second job), but it was never decided. Should
raising work against a terminal complaint be refused — and if so, refused in
the RPC with an `HB409`, or merely hidden by the screen?

## 11. Added 2026-08-20 — may a complaint have no description?

**Why this is here and not simply fixed.** `POST /api/v1/complaints` was
failing 400 on the hosted project. Diagnosing it turned up three hosted-schema
gaps, and two of them are pure drift with nothing to decide: the hosted
`complaint_events` has no `payload` and the hosted `complaints` has no
`aggregate_version`, both of which `0001_baseline.sql` declares and every
writer since has assumed. Adding them back is bookkeeping, and it is done —
`backend/supabase/migrations/20260820120000_hosted_complaint_column_drift.sql`,
with the evidence in
[`HOSTED_SCHEMA_DRIFT_COMPLAINTS.md`](HOSTED_SCHEMA_DRIFT_COMPLAINTS.md).

**The third gap is not bookkeeping.** The hosted `complaints.description` is
`not null`; the baseline declares it nullable. Two things currently disagree
about whether a complaint needs a description at all:

* the wire says no — `ComplaintCreate.description` is
  `_optional_text(4000) = ""` (`resident_complaint_schemas.py`:168), and
  `raise_complaint` turns the empty string into a real null;
* the hosted column says yes, and would raise `23502` for that null.

Nobody has seen this because the missing `payload` fails the same transaction
one statement later, for everyone.

**The default taken.** The patch drops the hosted `not null`, because the
repository's own declaration is the authority for reconciling drift and this
moves the column towards it rather than away. So today: **a resident may file a
complaint with a title, a category and nothing else.**

**What is yours.** Whether that is right. A complaint with no description is a
row a supervisor has to chase by phone, and the form could reasonably insist on
one — but that is a decision about what a complaint *is*, and it belongs to you.
If you want it mandatory, the change is on the wire (`_optional_text` →
required, plus the form), **not** by restoring the hosted constraint: a database
that rejects what the API accepts produces a 500 rather than a validation
message. The `not null` can come back afterwards as a second step, once nothing
can send an empty one.

**Also unasked, and cheap to answer now:** the hosted `complaint_events` still
carries the pre-baseline `previous_status`, `new_status` and `note` columns.
Nothing in the repository writes them, `dashboard_repository.py`:67 still reads
them in the legacy branch this project takes, and there were 0 rows in the table
on 2026-08-20 — so there is no history to migrate into `payload` and nothing was
backfilled. If the dashboard's legacy branch is ever retired, those three
columns go with it.

---

## 12. Added 2026-08-20 — the admin portal raises complaints, and an admin with a flat is a resident

**Read this section differently from §§1–5 and §§8–11.** Those record defaults we
took because nobody had ruled. This one records **rulings that were made**, by the
product owner, on 2026-08-20, and implemented the same day. They change how a
complaint is owned and who may act on one, which is your surface. Nothing here is
asking you a question; the two questions this work *did* raise are at the end and
are marked as such.

A complaint of ours now touches your engine in one new place, and the migration
is `backend/supabase/migrations/20260820150000_admin_raised_complaints.sql`
(applied by hand by the repository owner in the Supabase SQL editor, per the rule
in `backend/supabase/migrations/README.md`).

### The four decisions

**D1 — An admin with a flat is the resident of that flat.** There is one
`community_memberships` row per person per community
(`memberships_active_person_community`, `0001`:45), so the administrator who owns
B-402 has one membership and its role says `admin`. Guarding the resident verbs
with `require_membership_role("resident")` refused that person the verbs on their
own home — cancel a visit, confirm a resolution, answer a proposed slot. The guard
is now `require_resident_capability` (`app/api/deps.py`): the `resident` role, or
one active `unit_residencies` row on the membership. **Resident-ness is that row
and never a role implication.** The refusal is byte-identical to the old one —
`403`, `community_role_required` — so nothing on the wire moved.

`GET /auth/session` was corrected in the same direction: it granted every admin
the `resident` capability outright, which made the session disagree with a guard
asking the same question of the same table, so a flat-less admin was shown the
resident affordances and then refused when they used one. It now grants it only
with an active residency.

**D2 — Admins raise complaints from the admin portal, in two modes.**
`POST /api/v1/complaints/admin-raise` (`require_admin` + CSRF, `201
{id, message}`), backed by `public.admin_raise_complaint(...)`. One optional field,
`forMembershipId`, decides which mode:

| | Owner (`raised_by_membership_id`) | `raised_via` | Visible on |
|---|---|---|---|
| **On behalf of a resident** | that resident's membership | `resident` | their resident portal, with every resident verb — plus the admin queue |
| **Attached to no flat** (amenity, lobby, gate) | the admin's own membership | `admin` | the admin queue only |

The first is a resident who telephoned the office. It is **their** complaint: they
confirm, reopen and cancel, because the alternative is a complaint about their
home that they cannot act on. The second is a lobby light — somebody has to own
the row, the person who noticed is the honest answer, and it is kept off that
admin's own "My Complaints", which means *what happened to me at home*.

**D3 — Provenance lives in the `raised` event, not in the complaint row.** The
event's `actor_membership_id` is **always the admin**, in both modes, and the
payload carries `"on_behalf": true` when filing for somebody. Writing the resident
into the actor would forge a history entry, which is the one thing an append-only
timeline exists to prevent. And keeping "an admin typed this" out of the complaint
row is what stops it from ever being a reason to move the complaint off the
raiser's list.

`complaints.raised_via` (`text not null default 'resident'`, CHECK in
`('resident','admin')`) is therefore **not** provenance. It answers one narrower
question — *which portal owns the raiser-side view* — and it is derived by the
RPC from `p_for_membership_id`, never accepted from the client.
`complaint_overview` was recreated to expose it, and `list_mine`/`get_mine` in
`resident_complaints_repository` filter `raised_via = 'resident'`.

**D4 — The resident raise now requires the resident capability.**
`POST /complaints` previously required only an active membership. **This is a
narrowing and it is the one thing in this section that can break somebody**: a
`worker`, `security` or `manager` membership with no residency could file onto a
resident complaint list and now gets `403 community_role_required`. Their path is
`/admin-raise` if they are an admin. No screen outside the resident portal calls
`POST /complaints` (checked across `frontend/src/**` on 2026-08-20).

### What did not change, deliberately

`raise_complaint` is untouched — not replaced, not re-created, no new overload.
The routing (`resolve_complaint_department`), the priority-derived SLA, the
`notify_complaint_staff` audience and the supervisor → work order pipeline are
the same code paths for both raises. **An admin-raised complaint is a complaint**,
and §§1–5 apply to it unchanged.

### Addendum, later on 2026-08-20 — both hands on an on-behalf complaint

**DECISION (product owner):** when a complaint is raised on behalf of a resident,
**both** the resident and the admin should hold the lifecycle verbs — cancel,
reschedule, and the like. An action from either is valid, and whoever acts first
gets that action; the other side simply finds it already done.

What exists today falls short of that on the admin side, and the gap is yours to
design:

* The **resident's** half already works: the on-behalf complaint is owned by the
  resident (`raised_by_membership_id`), so every ownership-keyed resident verb —
  cancel, reopen, confirm-resolution, and the schedule-slot pick — accepts them.
* The **admin's** half does not: `PATCH /complaints/{id}` accepts only
  `Pending | In Progress | Resolved` (`UpdateComplaintRequest`), so an admin has
  **no cancel and no reschedule verb at all** — not on on-behalf complaints, not
  on their own unit-less ones. Whether to widen the PATCH's status set, expose
  the resident verbs to admins, or add admin-specific endpoints is a shape only
  you should choose; whichever you pick, the timeline entry should carry the
  true actor, as the raised event already does.
* **First-wins needs no new machinery** if the write goes through the same
  status-transition validation the resident verbs use — the second actor's
  now-invalid transition is refused, which is exactly the ruling.

### Two questions that were yours — both now have answers

**Q12.1 — nobody tells the resident a complaint was filed for them.**
**ANSWERED (product owner, 2026-08-20): yes, notify the resident.** The
question below is kept for its context; the *mechanism* — whether it's the
general rule (*notify the raiser when the actor is not the raiser*) or a special
case in `admin_raise_complaint` — is still your design choice, and nothing has
been implemented. The original question:

`admin_raise_complaint` calls `notify_complaint_staff`, exactly as
`raise_complaint` does, which reaches the community's admins and the complaint's
department manager. Neither function notifies the **raiser** — correct when the
raiser is the person who just pressed the button, and arguably wrong here: a
resident who telephoned the office now has a complaint with an SLA clock, a
timeline and three verbs they can use, and no in-app signal that any of it
exists. The default was taken by inheritance rather than chosen, and the shape is
yours: should the on-behalf mode notify the owner, and if so is that a general
rule (*notify the raiser when the actor is not the raiser*, which would also
cover any future admin action on somebody's row) or a special case in this one
function?

**Q12.2 — has `raise_complaint` left an orphaned overload on the hosted
database? Nothing here can answer that, and it is worth one query of yours.**
**CLOSED (2026-08-20): no orphan.** The product owner ran the `pg_proc` query
below against the hosted database right after applying
`20260820150000_admin_raised_complaints.sql`, and it returned exactly two rows —
`raise_complaint(uuid,text,text,text,text,text,uuid,uuid)` (the eight-argument
current version) and `admin_raise_complaint(uuid,text,text,text,text,text,uuid,uuid,uuid)`
(the new nine-argument function). No surviving six- or seven-argument overload.
The paper trail and the live database agree; nothing to drop. The original
write-up is kept below for the method, since the same PostgREST blind spot
applies to any future function replacement:

This was raised to us as a probable defect — *"`20260812090300` replaced
`raise_complaint` at a different arity without dropping it"* — and **reading the
files says otherwise**, so the claim is recorded here as checked and not upheld
rather than passed on:

* `0031`:318 creates `raise_complaint(uuid, text, text, text, text, text)` — six
  arguments.
* `20260812090300_complaint_department_routing.sql`:271 **drops exactly that
  signature** before creating the seven-argument version.
* `20260813100000_skill_sourced_complaints.sql`:75 **drops exactly the
  seven-argument signature** before creating today's eight.

Both hand-offs are clean on paper, and the eight-argument function is the one the
hosted probe found (`HOSTED_SCHEMA_DRIFT_COMPLAINTS.md`, "functions — all present,
all at the right arity").

**What is still unverified is narrow and real.** That probe reads PostgREST's
schema description, which lists **one entry per RPC name**, so it cannot show an
overload if one existed — a surviving `raise_complaint(6)` would be invisible to
every check this project has run, and `0031`:410 granted `execute` on it to
`authenticated`, so it would be reachable rather than merely present. The only
thing that answers it is `pg_proc`:

```sql
select oid::regprocedure from pg_proc where proname = 'raise_complaint';
```

One row is the expected answer. If there are two, the extra one is the `0031`
body — older routing with no `department_id`, and the pre-routing notification
audience — and it should be dropped by its exact signature in a migration of
yours. **We did not attempt it either way**: `raise_complaint` is your function,
and dropping one on a live database on the strength of a claim we could not
reproduce is precisely the kind of decision this file exists to hand over instead
of taking. The failure mode is written up in `20260813100000`:12, and
`admin_raise_complaint` opens with the same exact-signature drop for the same
reason — today it is a no-op, and it is there so that re-running the file cannot
become the next overload.

---

## 13. Added 2026-08-12 — the rulings: every question in §§0–10 now has an answer

*(Merged from the `services-and-security` line on 2026-08-20. This section
predates §§11–12, which were written 2026-08-20 and are **not** covered by
these rulings — their open questions, and the §12 addendum's dual-actor
design work, stand.)*

A structured decision session with the product owner settled all of this
file's open questions plus the new operational model. The full specification
is [`COMPLAINT_ENGINE_PRD.md`](COMPLAINT_ENGINE_PRD.md); its §12 is the
ledger. Mapping back to this file's sections:

| This file | Ruling |
|---|---|
| §0 coupling | Coupled, forward-only projection (R17) — PRD §6.1 |
| §1 work-done → resolved | The third shape: resolve when no other live job (R4) |
| §2 auto-resolution | 72h auto-close from `resolved`, 48h reminder, reopen survives (R11) |
| §3 vocabulary | CHECK-locked registry; four new types (R19) |
| §4 reopened → different supervisor | Retired: same queue, flagged, prior workers excluded (R12) |
| §5 priority re-inheritance | Unchanged, still manual (out of scope) |
| §8 / §10 assignment fork | Option 1: the control raises work; the optimistic field dies (R13) — **executed 2026-08-21**, see §15 ruling 6 |
| §9 transfer consent | Unchanged: notify after the fact (R16) |
| §10 work on ended complaints | Refused in the RPC, HB409 (R14) |

Beyond this file's questions, the same session ruled: manual-first assignment
with worker consent and a 2h/24h auto-dispatch fallback (R1, R7), `high` is
the critical tier (R2), forced assignment best-ranked-instant after
all-declined on high only (R8), freeform in-chat price negotiation (R3),
slot-first scheduling kept (R6), one skills catalogue feeding both the raise
dropdown and onboarding (R5), resident cancel until work starts with a
re-evaluation pool and per-complaint worker exclusion (R9, R10), transfers
refused while work is live (R15), and supervisors now notified on raise (R18 —
recorded as settled here on 2026-08-13 and **actually implemented 2026-08-21**;
see §15 ruling 7 for what shipped in between, which was nothing).

---

## 14. Added 2026-08-21 — who may still *read* a complaint after they leave

**Not a lifecycle change. Nothing about `complaints.status`, the timeline, the
transfer rules or the dispatch chain moved.** This is here because two of the
2026-08-21 access-scoping fixes change what a departed supervisor can read of
your surface, and access to a complaint is close enough to your boundary that
deciding it silently would be exactly what this file exists to prevent.

**The ruling.** *"Once a supervisor/manager is removed from a community and later
invited to a different one, they must not be able to see ANYTHING from the old
community — engagements, complaints, conversations/messages, calendar,
notifications, anything their portal reads."* (Product owner, 2026-08-21.)

**Your complaint reads were already correct and were not touched.**
`department_complaints`, `department_change_requests`, `unassigned_complaints`
and the two decision RPCs all guard on `can_supervise_department` or
`is_community_admin`, and both of those already require an **active** roster row
*and* an **active, unended** membership (`0036` §4, `0019` §0). A supervisor
removed from community A stops passing them the moment
`remove_department_member` runs. No change was made to any of them, and none is
needed.

Three things that touch complaint *data* did change, and here is each one with
what it costs you:

1. **`is_own_staff_assignment` now requires the roster row and the membership to
   be live.** It is one of the four arms of `can_read_work_order`, so a worker
   who has left a community stops being able to read the work orders they held
   there — and therefore the complaint titles and resident details those work
   orders carry (`my_worker_job` projects `complaint_title`,
   `complaint_description`, `resident_name`, `resident_phone_e164`). **The
   complaint itself is untouched**: `complaints` has its own policies, the
   department still reads every row, and nothing about who *owns* a complaint
   moved. What ended is one departed person's window onto it.

   *The cost, stated plainly:* a worker who leaves loses their own history. Last
   month's completed jobs vanish from their calendar with the community. That is
   what "removal severs access completely" means and it is the ruling rather than
   an oversight — but if the complaint engine ever wants a "work I have done"
   read that outlives an engagement, it will need its own predicate rather than
   this one, and this paragraph is the reason why.

2. **The direct-message policies now require an active membership in the thread's
   community.** `open_work_order_thread` is the resident↔worker channel for a
   live job, so this is the worker's side of a conversation *about a complaint*.
   The thread and its messages are not deleted and the resident still reads the
   whole conversation; what ends is the departed worker's access. `0046`'s lock
   trigger (a thread closes when its work order goes terminal) is unchanged.

3. **The notification feed now hides rows keyed to an ended membership.** Several
   of those rows are yours — `complaint.assigned`, `complaint.transferred`,
   whatever the engine sends next. A removed supervisor stops seeing community
   A's complaint notifications. This **overturns a decision `0041` recorded**
   ("a notification is a copy of something the person was already told, and every
   inbox in the world retains those"), and the overturn is named in
   `CHANGE_LOG.md` as the convention requires. If the engine ever needs a
   notification to survive its recipient's departure, write it with
   `notify_profile` rather than `notify_member`, or let `notify_member` do it for
   you — it now files a message addressed to an **already-ended** membership
   against the person and no community, which is how the "you were taken off a
   roster" farewell survives.

**One question we did not answer, because it is yours.** A supervisor is removed
from community A while holding open complaints assigned to them.
`remove_department_member` refuses the removal while any **work order or shift**
is still booked in their name (`0043` §9) — but `complaints.assigned_to_
membership_id` is not counted by `staff_open_commitment_count`, and nothing in
the departure flow reassigns it. So a departure can complete leaving complaints
pointing at a membership that has ended, and `department_staff_overview`'s
`active_assignment_count` will keep counting them against a roster row that is
now inactive. Nothing we changed makes this worse or better; the access scoping
above simply makes it visible, because the person it names can no longer open
them. Whether an approved departure should also clear or reassign
`assigned_to_membership_id` is a lifecycle question and we have not touched it.

> **Answered the same day — see §15, ruling 1.** The product owner ruled that
> complaints stay department-pooled and that nothing new writes
> `assigned_to_membership_id`, which dissolves the question rather than deciding
> it: the column has one writer and no reader, so there is no per-person
> complaint ownership to reassign. Two details in the paragraph above are stale
> as a result. `active_assignment_count` did not "keep counting them" — it
> counted nothing, ever, and ruling 5 removed it. And what a removal actually
> strands is the *work orders* those complaints spawned, which ruling 2 now
> re-stamps.

---

## 15. Added 2026-08-21 — the product owner's rulings on removal continuity

**This section answers §14's open question and eight others.** The user (Lee
Johns) took the product-owner role for the complaint engine on 2026-08-21 and
made every ruling below explicitly, in one sitting, after reading §14. They are
recorded here rather than only in `CHANGE_LOG.md` because seven of the nine
constrain what this engine may become, and a constraint that lives only in a
change log is one the next author reads after they have already designed around
it.

Every ruling is **frozen**. Where one overturns something, it says so.

---

### Ruling 1 — complaints stay department-pooled. §14's open question, closed.

> *"A complaint belongs to the department, not to a person. Nothing new writes
> `assigned_to_membership_id`."* (PO, 2026-08-21.)

§14 ends by handing you a question: a departure can complete while complaints
still point at the membership it ended, and whether an approved departure should
clear or reassign `assigned_to_membership_id` is a lifecycle decision. The answer
is that **the question dissolves rather than being answered**, because the column
it is about is not the model.

`complaints.assigned_to_membership_id` has exactly one writer — `update_complaint`
(`0031` §668, the write at §715, with a `coalesce` that means it can never be
cleared) — and **no reader anywhere**. No frontend calls `PATCH /complaints/{id}`
with it. The admin portal's "Assign to staff" dropdown never touched it either
(see ruling 6). So there is no per-person complaint ownership in this product,
there never has been, and none is being created.

What this costs you: nothing you had. What it buys: the removal problem stops
being "how do we move N complaints" and becomes "how do we move the work orders
those complaints spawned", which is ruling 2 and is a much smaller question,
because a work order already names a supervisor and already has a lifecycle.

**Consequence for §14's last paragraph.** It is now stale in one detail and you
should read it with this beside it: `department_staff_overview.active_assignment_count`
does not "keep counting them against a roster row that is now inactive". It
counted nothing, ever — see ruling 5 — and the column is gone.

---

### Ruling 2 — removal continuity is work-order re-stamping.

> *"When someone is removed, the live work they supervise goes to whoever is left
> — another supervisor if there is one, the manager if there is not."*
> (PO, 2026-08-21.)

**The defect this repairs is not one this file predicted.**
`work_orders.supervisor_membership_id` (`0036` §1, stamped at §742) is the
delivery address for five notification kinds:

| Kind | Written by |
|---|---|
| `work_order.no_candidates` | `20260812120000` |
| `work_order.resident_accepted` / `_declined` | `0036` |
| `work_order.accepted` | `0039` |
| `work_order.completed` | `0039` |
| `work_order.failed` | `0039` |

Nothing re-pointed that column when the person it named stopped being a
supervisor. Before 2026-08-21 the consequence was a message delivered to somebody
who had left; after `20260821140000` §8 scoped the notification feed to live
memberships, the consequence is a message **written and instantly invisible**. A
department's live jobs report their progress into a mailbox nobody can open, and
nothing errors.

**The target rule, as implemented** (`20260821200000`,
`department_supervision_successor`):

1. the **least-loaded remaining active supervisor** of the same department whose
   own membership is live — ties broken by `created_at` then `id`, so the choice
   is deterministic and re-running the repair moves nothing;
2. else the department's **manager**: the roster row holding `rank = 'manager'`,
   then a `manager` membership pinned to this department, then one pinned to no
   department (which `can_manage_department` reads as "manages any");
3. else **nobody**, and the work orders are left exactly as they are.

Step 3 is a decision and not a gap. A wrong address is worse than a stale one:
the stale one at least names the person the department remembers assigning the
job to. Community admins are deliberately not a step — they are not on the
department's roster, and `supervisor_membership_id` is the department's own answer
to "whose job is this".

**Scope.** Live work orders only (not `completed`, `cancelled`, `failed`) and only
within the department the roster row belonged to. Renaming a finished job
falsifies a record; and a membership can appear on more than one department's
work, which re-stamping by membership alone would hand entirely to whichever
department lost them first.

**Residents and workers see nothing, by construction.** No resident-facing or
worker-facing read has ever returned a supervisor's identity
(`resident_complaints_service.py` §194/§226, `20260813105000` §34–63). This is
worth knowing rather than re-deriving: it is why re-stamping needed no
notification suppression and no "the supervisor changed" event.

**Where it lives, and why that matters to you.** An `after update` trigger on
`staff_assignments`, not an edit to `remove_department_member`. Removal has four
RPC entry paths and a fifth that is not an RPC at all —
`staff_assignments_admin_write` is `for all to authenticated` with direct grants
(`20260812200000`), so an admin can flip `status = 'inactive'` through PostgREST
without touching a function. All five end at the same `update`. If the engine
ever adds a sixth way for somebody to stop supervising, it gets continuity for
free provided it goes through that column.

---

### Ruling 3 — the last supervisor's departure is a notification and a banner. Not a new screen.

> *"Tell the manager they're covering it, and show them so on the complaints
> screen. Don't build them a supervisor workspace — they already have more than
> the supervisor does."* (PO, 2026-08-21.)

When the removed row was the department's last active supervisor, the manager and
the community's admins receive one `department.supervision_uncovered` notification
— *"You are covering …'s complaint queue"* — and the manager's Complaints screen
carries a banner for as long as the department has no active supervisor.

**The "no new workspace" half is the load-bearing half.**
`can_manage_department` implies `can_supervise_department` (`0036` §435–454, first
line of the body), so a manager already passes every guard on every supervisor
surface, and `/manager/complaints` (`ManagerDashboard/Complaints.jsx`) is a strict
superset of the supervisor's screen — it has the change-requests panel and the
move-department verb on top of the same list. Building a supervisor workspace for
the manager would be building a subset of what they already have.

**One restriction that is not obvious.** The notice fires only for
`departments.kind = 'service'`. A security department's manager lands in
`/security-manager`, which has no complaints screen and is not meant to — gate
work arrives as incidents and shift entries. Sending them a link that redirects
home is the failure `frontend/src/features/notifications/portalUrl.js` exists to
prevent. Re-stamping is *not* so restricted: a work order is a work order.

---

### Ruling 4 — removal gets a real confirmation dialog.

> *"You can't take someone off a roster behind a `window.prompt`."*
> (PO, 2026-08-21.)

Both roster verbs used to open a `window.prompt` asking for a reason, and the
prompt — by being the only thing in the way — doubled as the confirmation. So
Remove followed by Enter removed somebody having said nothing about what they held.
Replaced by a sheet in `ApproveModal`'s style that names the person and their rank,
states both real counts, warns when they are the department's last supervisor, keeps
the reason field as the optional thing it always was, and has an explicit Cancel.

The three-state button logic is unchanged — pending departure opens the handover,
booked items start one, otherwise Remove. The sheet is the confirm layer, not a
redesign of when each verb is offered.

---

### Ruling 5 — the always-zero roster count dies.

> *"'0 open complaints' on every row is not a number, it's a decoration."*
> (PO, 2026-08-21.)

`department_staff_overview.active_assignment_count` (`0045` §1450, lateral at
§1455–1469) counted open complaints matching either `assigned_to_membership_id`
or a prefix match on `assignee_label`. Ruling 1 keeps the first column dead and no
frontend has ever written the second, so the number was `0` on every row of every
roster ever rendered — and the hiring screen displayed it as "N open complaints"
next to a real one.

Replaced by `supervisedWorkOrderCount`: the live work orders that person
supervises, `0` for anybody whose rank is not `manager` or `supervisor`. That zero
is the truth and not a placeholder — a team member's real number is
`openCommitmentCount`, which is on the same row. The old field is **removed rather
than renamed in place**, so a client still reading it gets `undefined` instead of
a wrong number.

---

### Ruling 6 — the admin "Assign to staff" control is removed. R13, executed.

> *"It doesn't assign anyone. Take it out."* (PO, 2026-08-21.)

This is not a new decision: **R13 is in this file's own ruling table** (§13,
*"Option 1: the control raises work; the optimistic field dies"*) and in
`COMPLAINT_ENGINE_PRD.md`'s, recorded as settled on 2026-08-13 and never done. The
control wrote `assigneeStaffId` into zustand and nowhere else — no server saw it,
no worker was told, and the roster panel beside it counted those local writes back
as "N active", a number the browser invented that did not survive a reload.

It is replaced by the link R13 named: *Raise work order*, deep-linked to the
triage screen with `?complaint=…`. That is the assignment that exists — a real
record, with a real recipient, that outlives a page reload.

**Worth noticing why it survived eight days.** A ruling recorded in a table and
not executed looks identical, in a later review, to one that was.

---

### Ruling 7 — supervisors really are notified when a complaint is raised. R18, implemented.

> *"R18 says supervisors are notified. They aren't. Make it true."*
> (PO, 2026-08-21.)

Also not a new decision. R18 — *"supervisors now notified on raise and reopen"* —
is in this file's §13 summary and in the PRD's ruling table. What shipped was
`notify_complaint_staff` (`20260812090300` §2b), whose audience is the community's
admins plus the complaint's own **department manager**, and stops there.

**Why the gap survived a review.** A supervisor is a *rank on a roster row in one
department*, deliberately (`0043` §386 argues the point at length), so no
role-based helper can express them — and a reviewer reading the audience as
"admins and managers" finds it correct, because it is, for the audience it names.

The arm added is `notify_department_leadership`'s own predicate narrowed to the
complaint's department, `distinct`, excluding admins so nobody is told twice. It
is in the shared helper rather than at the raise call site, so it holds for every
complaint-shaped event this engine has: the resident raise, the admin raise, a
reopen, a resident's cancellation, a forced assignment and an all-declined.

---

### Ruling 8 — the invitation claim pass runs on every session read.

> *"Someone who already lives here should still get their invitation."*
> (PO, 2026-08-21.)

Not strictly complaint-engine, and recorded here because it changes who can become
a supervisor at all. `auth_service._claim_staff_invitations` was called only on
the branch that had already established the caller holds no membership. Anybody
who already belonged to a community — a resident invited to supervise a
department, a worker on one roster invited to manage another — never reached it.
Their invitation was neither applied nor refused: it waited, invisibly, while the
inviting department went on seeing `pending`.

After `20260821140000`/`20260821170000` the refusal half matters as much: an
invitation that *cannot* be applied is marked blocked and both sides are told, and
that announcement was reachable only by the same narrow population. The guard is
gone. Cost: one GoTrue identity call and one idempotent RPC per `GET /auth/session`
— a load-time read, not a per-request path.

---

### Ruling 9 — the serviceman release mechanics are untouched.

> *"The re-queue is right. Leave it alone."* (PO, 2026-08-21.)

`release_staff_commitments` puts a departing person's booked work back into the
dispatch pool at **queue priority 1 — just below urgent auto-assigns at 2**
(`0045` §7, `0043`). That is what the owner wants and it is recorded here so
nobody re-opens it while working on ruling 2. `claim_dispatch_batch` and the
dispatch engine are likewise out of bounds; the migration that implements rulings
2, 3, 5 and 7 mentions none of the three, and a static test asserts as much.

---

### What is still yours

Nothing in this section moved `complaints.status`, the timeline vocabulary, the
transfer rules, the auto-resolution timers, or the dispatch chain. Rulings 2 and 3
sit entirely on the *work order* side of your boundary and on the roster row that
names its supervisor. Ruling 7 widens an audience without changing a single event.
Ruling 1 removes a question you were owed an answer to rather than answering it in
your place.

---

## 16. Added 2026-08-21 — the deep link now highlights on your admin screen

**One ruling, and it touches a file of yours, which is why it is here rather
than only in the change log.**

> *"A `?complaint=` link must show me which complaint. Do it on the admin screen
> and the supervisor's screen. Leave the resident one — that portal is still the
> demo."* (PO, 2026-08-21.)

Eight notification call sites — six in `20260812090300_complaint_department_routing`,
one in `20260813100000_skill_sourced_complaints`, one in
`20260820150000_admin_raised_complaints` — write `/admin/complaints?complaint={id}`.
`AdminDashboard/Complaints.jsx` read no query parameter, so following one landed
the reader on a queue of up to two hundred cards with nothing saying which. Right
screen, wrong row — the defect `backend/tests/test_notification_links.py` counts
in `IGNORED_QUERY_PARAMETERS`, where `("/admin/complaints", "complaint")` had sat
since that check was written, attributed to you. It has now left that set.

**What was done to your screen, exactly.** It reads `?complaint=` and marks that
one card: `border-2 border-indigo-400 bg-indigo-50/40` in place of the usual
hairline border, `aria-current="true"` so the mark is not colour-only, and a
scroll into view once the snapshot has arrived. **Marked, never filtered** — the
same rule `features/complaints/components/DepartmentComplaintList` and
`WorkOrderTriage`'s `?job=` already follow, because a queue narrowed to one card
hides the rest of an inbox somebody still has to work. The status filter is
untouched and still mounts at *All*.

**What was not done.** No complaint lifecycle behaviour, no mutation, no route,
no vocabulary, no status write, no change to the raise modal or the triage
queue. `complaints.status` is where §0 left it. This is a highlight on a card and
the record of a ruling; if you would rather mark the row some other way, the
ruling constrains the *outcome* — the reader can see which complaint — and not
the treatment.

The supervisor's screen (`WorkerDashboard/Complaints.jsx`) is the same ruling's
other half and needed no new idea: it already renders
`DepartmentComplaintList`, which has taken `highlightId` and ringed that card
since the manager's screen was built, and simply never passed the prop.

**The resident screen is deliberately deferred**, not forgotten.
`("/resident/complaints", "complaint")` stays on record in that same set. The
resident portal is still a zustand dummy-data demo
(`docs/potential issues/09-resident-portal-is-still-a-demo.md`), so highlighting
a row there would demonstrate nothing about the link that a reader will actually
follow. When that portal is wired to the API, the entry is the reminder.

## 17. Added 2026-08-22 — your Save button was accused of writing nothing; for the record, it writes everything

A specialist report flagged, in passing, that `AdminDashboard/Complaints.jsx`'s
*Save Changes* and comment controls "write to zustand only — no server call".
You may hear this rumour; here is the verification that killed it, so nobody
spends an afternoon on it again.

**The chain is real, end to end.** `store/slices/createComplaintsSlice.js`
follows its optimistic store write with `PATCH /complaints/{id}` and
`POST /complaints/{id}/comments`. Both routes exist in
`backend/app/api/v1/routers/complaints.py` behind `require_admin`; the service
translates the screen's vocabulary (`In Progress` → storage status, `resident`
→ `public` visibility) and writes the edit with its timeline entries in one
transaction; both writes fire the shared SSE trigger, and
`DashboardDataBootstrap` re-snapshots the dashboard within a beat, replacing
the optimistic copy with what your engine actually recorded.

**The one true gap, fixed 2026-08-22 (PO-approved).** A *failed* write fires no
SSE event, so the refused state sat on the card indefinitely with only a
transient toast against it. The slice's catch now re-reads the snapshot for
server truth, falling back to restoring the affected row locally when even that
read fails. No lifecycle behaviour, vocabulary, route or mutation of yours
changed — this is purely what the screen shows after your engine says no.

**A note you may care about more than the fix.** The screen's "Staff /
Assignee" box is free text, persisted as a display label (`assignee_label`) and
nothing else: it never sends `assigned_to_membership_id` (which §15's ruling 1
keeps dead) and drives no dispatch — real assignment lives in the work-order
pipeline. So the label can *say* "Suresh — Electrician" while the pipeline has
routed the work elsewhere, and nothing reconciles the two. Whether that box
should keep existing, rename itself to something honest ("shown to the resident
as…"), or derive from the work order is a judgement about your surface; it is
recorded here rather than decided.

## 18. Added 2026-08-22 — nobody could raise a work order, and the supervisor dashboard rulings

**The break first, because it was yours to feel.** Every `POST
/complaints/{id}/work-orders` — the "Raise it" button in triage, supervisor and
admin alike — answered 422 "Could not raise that job." The cause is not in your
engine and not in the repository at all: the hosted `work_orders` table is the
pre-baseline hand-built one and carries legacy columns no migration declares,
one of which (`title`, NOT NULL, no default) rejected every insert
`create_work_order` writes. Same disease `20260820120000` cured on
`complaints`. The cure is the same shape:
`20260822090000_hosted_work_order_column_drift.sql` (runbook §17) drops the
insert-blocking legacy NOT NULLs and nothing else — your RPCs, vocabulary and
lifecycle are untouched, because they were never wrong. Until it is applied,
raising work stays broken for everyone. Two diagnostic improvements rode
along: `pg_errors.translate` now logs the real Postgres text server-side for
mapped standard SQLSTATEs (this bug was undiagnosable without it), and the
triage screen's error line renders the 422 envelope's field `details`.

**The supervisor dashboard rulings (product owner, 2026-08-22).** The
supervisor's landing surface is being rebuilt as four sections: new complaints
(urgent stack on top, category and priority chips), taken-up-but-unassigned,
assigned-but-pending, and being-worked-right-now. Four decisions touch your
model; all are the product owner's, taken 2026-08-22:

1. **Take-up is explicit and stamped.** A supervisor presses *Take up* on a new
   complaint; new columns `complaints.taken_up_by_membership_id` +
   `taken_up_at` record it, and a new `take_up_complaint` RPC (guarded
   `can_supervise_department`) is the only writer. To be explicit against
   §15's ruling 1: this is *triage ownership*, not dispatch —
   `assigned_to_membership_id` stays dead, the complaint still belongs to the
   department, and dispatch still happens only through work orders.
2. **Take-up is visible progress.** It moves the complaint `open →
   acknowledged`, which the resident already reads as "In Progress". Until
   now `acknowledged` was written only by the worker-offer trigger
   (`20260813102000`); it gains this second writer deliberately.
3. **Re-stamped work is marked now.** §16 chose "no new column" for
   departure-continuity re-stamping. That is partially reversed: work orders
   gain `supervision_inherited_at`, stamped by `restamp_department_supervision`,
   so an inheriting supervisor's dashboard can badge work that arrived by
   removal rather than by their own hand. Residents and workers still never
   see supervisor identity; the stamp feeds a supervisor-only surface.
4. **"Being worked right now" is the worker's own Start.** `start_work_order`
   gains a `started_at` stamp (today the moment is lost into `updated_at`).
   A *Pause* verb is deliberately deferred — a paused state would ripple
   through your status vocabulary and the dispatch triggers, and the section
   stands without it.

The other two "reassigned" badges ride on what you already expose:
`returned_to_pool_at` / `reopened_count` for bounced-back work, and the
department-change events for complaints rerouted in. One new aggregate read,
`supervisor_triage_snapshot`, will feed all four sections in one call rather
than the N+1 the triage screen does today; it is a read, it decides nothing.

5. **The take-up timeline wording is frozen** (product owner, 2026-08-22,
   approved verbatim). The `taken_up` event renders on the resident's
   timeline as label **"Taken up by the department"** with message **"The
   department has taken this up."** — deliberately the `job_created` pattern:
   the department speaks, no supervisor is named, consistent with residents
   never seeing supervisor identity anywhere on your surface. Lives in
   `resident_complaints_service.py`'s label/message maps.

## 19. Added 2026-08-22 — your event vocabulary has a bouncer, and the new word was not on the list

Same-day follow-up to §18, recorded because the constraint is yours. Your
`20260813105000_chat_autopen_and_vocab.sql` put an enumerating CHECK
(`complaint_events_type_check`) on `complaint_events.event_type` — a good
bouncer. The §18 dashboard work added a `taken_up` timeline event, reasoned
from the `0001` baseline ("event_type is text with no CHECK"), and missed
your constraint entirely; the very first live Take-up press was refused with
SQLSTATE 23514.

The cure is `20260822150000_taken_up_event_word.sql` (runbook §19): your
constraint recreated in your file's own drop-and-recreate shape, with
`taken_up` as the one new word — your twenty-five words all survive, proved
by derivation in `backend/tests/test_taken_up_event_word_migration.py`
rather than by anyone's review.

What this means for you going forward: **any new `complaint_events` word now
costs a constraint migration**, not just a label in
`resident_complaints_service._EVENT_LABELS`. That is the deal your
`20260813105000` set up, and it is a good deal — the bouncer caught exactly
what it exists to catch — but the §18 migration's in-file comment saying a
new word is free is wrong, and this section is the correction of record. No
judgement call was taken from you here: the vocabulary decision (that
`taken_up` exists, and what the resident reads) was already ruled in §18;
this only lets the database agree.

## 20. Added 2026-08-22 — the supervisor dashboard grows hands, and six rulings touch your engine

The §18 dashboard was read-mostly: one button (Take up), four sections. The
product owner has now approved an action surface on it — the full design is
frozen as Amendment 2 of `docs/plans/SUPERVISOR_TRIAGE_SPEC.md`, and this
section records the rulings that reach into your lifecycle. All six were
ruled explicitly by the product owner on 2026-08-22; nothing here was
decided silently.

1. **Supervisors can now resolve.** A new RPC path
   (`supervisor_resolve_complaint`, guarded by `can_supervise_department`)
   sets `resolved` + `resolved_at`, writes your existing `status_changed`
   word, and notifies `complaint.resolved`. Your resident aftermath is the
   deliberate next act, untouched: confirm-with-rating to `closed`, reopen,
   48h warning, 72h auto-close. **Cascade ruling**: resolving cancels every
   unstarted live work order (offers withdrawn, staff notified
   `job.cancelled`, reason "Complaint resolved by the department") and
   refuses with a clear 409 while any job is `in_progress`.
2. **Complaint priority is no longer immutable.** A one-way raise
   (low → medium → high) with a **new event word `priority_changed`** —
   under §19's deal, that word ships inside a constraint rebuild in the
   migration, not as an assumption. Known and intended: raising to high
   arms your engine's automatic force-assign on the all-declined path.
3. **`note_added` gains an internal variant.** Supervisor notes carry
   payload `{internal: true}` and are hidden from the resident timeline;
   your admin PATCH's resident-visible "Update from management" notes are
   unchanged. The filter lives in `resident_complaints_service`.
4. **Complaints get a chat thread.** New `dm_threads.kind = 'complaint'`
   (one per complaint, raiser + department supervisor), locking on
   `closed|cancelled` like job threads. It lives beside your timeline, not
   in it — no complaint event is written for chat.
5. **Manual force-assign gets a hand on the lever.** A supervisor-triggered
   endpoint over your forced mechanics: `is_forced = true`, your existing
   `job_force_assigned` word, your `job.force_assigned` notification,
   still hidden from the resident timeline. The consent-respecting offer
   flow stays the default; force is an explicit flag.
6. **Resident-facing copy, approved verbatim**: "The department raised the
   priority to {level}." (timeline), "The department opened this chat about
   '{title}'." (chat seed), "Complaint resolved by the department."
   (job-cancel reason workers see).

## 21. Ruled 2026-08-23 — the v2 reconciliation is accepted as-is, including the away-until drop

Recorded here because the file it rules on is yours. The reconciliation itself
was never written up in this document — it lives in `docs/CHANGE_LOG.md` under
*Complaint Engine v2 branch reconciled forward* and, as of today, in runbook
§23 — so the short version comes first and the ruling second.

**What was reconciled.** The `complaint-engine-v2` branch carried its database
repairs as two backdated migrations, at versions *below* one hosted had already
applied. Those were dropped and their content re-authored forward as
`20260823120000_complaint_engine_v2_repairs.sql`, which reached this branch in
the 2026-08-23 merge (PR #46) and is **not yet applied to hosted**. It replaces
six bodies over five names: `sync_dispatch_tasks`,
`project_complaint_from_jobs`, both `dispatch_candidates` overloads,
`work_order_candidates` and `dispatch_force_assign`. An overlap audit against
§18's and §20's migrations found the intersection empty — nothing of the
supervisor triage or actions work is redefined by it.

**The ruling.** The complaint-engine owner reviewed all four behaviour changes
on **2026-08-23** and **accepts them as-is**. Nothing was sent back:

1. the manual-window queue priority is cast to `smallint`, which is the type
   `enqueue_dispatch_task` has always taken;
2. `project_complaint_from_jobs` resolves which of its two tables a row came
   from before reading it;
3. `dispatch_candidates` gains a three-argument overload that admits a worker
   who declined *this* work order — the two-argument form every existing caller
   uses stays strict;
4. `dispatch_force_assign` picks through `dispatch_candidates` instead of
   `work_order_candidates`, so a critical fallback running inside a *worker's*
   decline transaction is not refused by a supervisor-facing authorization
   check before it can select anybody.

**Explicitly included in that acceptance: (4) also drops the old
`away_until is null or away_until <= now()` filter, and that is intended.** The
old picker removed anyone *currently* inside a leave block whatever the job's
slot; `dispatch_candidates` already excludes a worker whose unavailability
**overlaps the slot being scheduled**, which is the question that decides
whether they can do the job. A worker on leave today but free next Tuesday was
being refused a next-Tuesday critical force-assign for no reason the schedule
knows about. **Only slot-overlapping unavailability blocks a critical force
assignment.** The consent-respecting offer flow is untouched and remains the
default; force stays an explicit flag, and §20's
`force_assign_work_order` — the supervisor's hand on the lever — reaches this
same mechanism through a call, which is why replacing one side left the other
standing.

Nothing here is a new judgement call being taken from you; it is the ruling on
four you were asked for, in one place, dated.

## 22. Ruled 2026-08-23 — the open-jobs board: workers get eyes, and hands

Live testing surfaced the gap from the worker's side of the counter: a freshly
hired plumber opened their portal and saw nothing, because in the model on
record a worker sees only what a supervisor has offered them. The product owner
ruled that this changes. Three rulings, taken 2026-08-23:

- **C1 — visibility.** Department roster technicians who hold the job's trade
  see the open-jobs board for their department. Not the whole roster, and not
  the marketplace: hiring remains the gate to a department's work, and the
  trade filter matches the one the offer path already applies.
- **C2 — claim is instant.** Taking a job from the board commits the worker on
  the spot, with the same mechanics as accepting an offer: an `accepted`
  assignment, the same status movements, the supervisor notified. First to
  claim gets it; there is no approval step.
- **C3 — unscheduled jobs are on the board.** A job with no hour on it appears
  with a "time to be set" marker and is claimable; the claim skips the
  slot-dependent eligibility checks (leave, windows, clashes — none of which
  can run without a slot) and the hour is set afterwards in the queue. This is
  deliberate: the alternative would have hidden exactly the job the owner
  raised in testing.

What counts as "open" (a job with a live offer out to somebody else, say) was
left to the orchestrator to adjudicate and log in the build spec. The board is
new read+claim surface only — the supervisor's offer and force-assign paths
are untouched by these rulings.

Related fix, same day: the force-assign picker's empty state blamed trades for
every empty candidate list, when `dispatch_candidates` returns nobody for any
job without a scheduled hour (its `job` CTE requires `scheduled_start_at is
not null` — 20260823120000, and by inheritance every earlier version). The
modal now names the missing hour and skips the fetch instead of misdiagnosing.

## §23. Ruled 2026-08-23 — the resident sets the time, and the system books what nobody schedules

Ruled by the product owner (live session, 2026-08-23), superseding the
raise-time model recorded in §12's era:

- **F1 — the raise form carries no date/time, for anyone.** A
  resident-subject job sends the RESIDENT a request to pick the date and
  time (a dashboard request, like a hiring application reaching a manager);
  only when they set it does the job reach the open pile. A facility job is
  auto-assigned by the system into the first available slot — but only
  after all urgent (priority `high`) resident complaints in the department
  have been allotted.
- **F2 — 24 hours of resident silence, then the system books.** If the
  resident has not picked within 24 hours of the raise, the system sets the
  first available time after the 24-hour mark that has a serviceman
  available, and assigns that serviceman automatically.
- **F3 — pick-mode has no decline.** The resident's card offers a time
  picker only; the decline button stays on the supervisor-proposed
  reschedule (approve-mode) flow. Silence is answered by F2.
- A new **"Awaiting resident response"** section on the supervisor
  dashboard surfaces the waiting jobs.

Orchestrator adjudications under these rulings (G1–G11), the frozen
interface, and the two-specialist split are in
`docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`. Engine-lifecycle notes for the
record: the supervisor-proposed approve flow survives untouched on the
reschedule path (awaiting_resident WITH a slot); pick-mode is
awaiting_resident with a NULL slot; the timeout handler branches on that
discriminator; and the facility gate re-checks hourly so a gated job is
never stranded (it stays claimable on the board throughout).

## §24. Ruled 2026-08-23 — only the servicemen pool holds a wrench

Ruled by the product owner (live session, 2026-08-23, on seeing the
supervisor and manager listed in the "Assign this job outright" picker):
**"its only asigned to the workers who are hired from the service men
pool."** Work orders may only be offered to, assigned to, auto-booked to,
or claimed by rank-`member` staff — the technicians hired from the
marketplace. Managers and supervisors never appear as candidates, to a
human or to the engine.

Engine impact: the single eligibility query (`dispatch_candidates_at`,
last defined in `20260823180000`) had no rank clause, so leadership leaked
into the picker, the slot-finder, the 24h auto-book, the facility
auto-assign, the ping, and — via `worker_open_jobs`/`claim_open_work_order`
— the open board. Because candidates order by fewest open jobs first, an
idle supervisor would have been the auto-book's FIRST choice. Fixed by one
`and sa.rank = 'member'` clause in the shared query plus the board's two
functions (orchestrator rulings R1–R3; the board-door closure R2 is
derived, flagged for PO confirmation). The same migration
(`20260823190000_assignment_write_repairs.sql`) also widens the hosted
`work_order_assignments` legacy NOT NULL drift that made EVERY assignment
insert crash (the live 422) — the auto-book and facility handlers would
have died on first fire without it. Full rulings and evidence in
`docs/plans/ASSIGNMENT_ELIGIBILITY_AND_DRIFT_SPEC.md`.

## §25. Ruled 2026-08-24 — the supervisor may pick up the wrench, but only on purpose

Ruled by the product owner (2026-08-24), confirming §24's derived
board-door closure (R2) and adding the rule's one deliberate exception:
**"yes, include an option where a super can take up work … it sholdnt be
something seen in normal routine workflow where the workers are hired and
present. it is available at any time though but as a seperate button
orsomething like that."** And on the thin-department consequence flagged
in §24's era: **"we assume that workers will eb availbale"** — no
automation fallback; a department with no technicians yields zero
candidates and the job waits; leadership take-up is the manual valve.

What this becomes (rulings R8–R14 in the assignment spec's 2026-08-24
addendum): a new verb, `take_up_work_order` in
`20260824090000_supervisor_take_up.sql`, exposed as
`POST /work-orders/{id}/take-up` and a quiet "Take this job myself" button
beside the primary assign action on the supervisor dashboard. The caller's
own leadership roster row is always the assignee — the verb cannot assign
anyone else — and every candidate surface (picker, auto-book, ping,
board) stays member-only.

Engine-lifecycle notes for your record:

- **One new timeline word, `job_taken_up`**, added to your
  `complaint_events` CHECK bouncer (§19's lesson: a word is a migration).
  It is written *beside* a normal `job_assigned` row, and R14 hides it
  from the resident timeline exactly as `job_force_assigned` is hidden —
  the resident's fact ("somebody is coming, and this is their name") is
  already on the row next to it. The worker/admin timeline labels it
  "Took up the job themselves".
- **§24's R7 attribution smell is closed** (R12): `force_assign_work_order`
  now stamps its two timeline events with the acting caller resolved from
  `auth.uid()` — the `take_up_complaint` pattern — instead of the raising
  supervisor's membership. Under manager-cover, force-assign and take-up
  events now name who actually acted.
- **The board refusal was reworded, not reopened** (R13):
  `claim_open_work_order` still refuses leadership with HB403, but the
  message now points at the sanctioned door.
- No status vocabulary, no dispatch_tasks kind, no transfer rule, no
  timer, and no `complaints.status` behaviour changed. The assignment row
  a take-up writes is `accepted / is_forced false / is_auto_assigned
  false`, so nothing downstream of your engine can mistake it for a
  forced or automated booking.

Migration hand-applied by the owner only; runbook §30 carries the
pre/post-checks. Verified 2026-08-24: backend 1472 passed / 5 skipped,
frontend 57 files / 384 tests, both on the orchestrator's own runs.
