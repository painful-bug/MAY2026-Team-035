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

---

## 11. Added 2026-08-12 — the rulings: every question above now has an answer

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
| §8 / §10 assignment fork | Option 1: the control raises work; the optimistic field dies (R13) |
| §9 transfer consent | Unchanged: notify after the fact (R16) |
| §10 work on ended complaints | Refused in the RPC, HB409 (R14) |

Beyond this file's questions, the same session ruled: manual-first assignment
with worker consent and a 2h/24h auto-dispatch fallback (R1, R7), `high` is
the critical tier (R2), forced assignment best-ranked-instant after
all-declined on high only (R8), freeform in-chat price negotiation (R3),
slot-first scheduling kept (R6), one skills catalogue feeding both the raise
dropdown and onboarding (R5), resident cancel until work starts with a
re-evaluation pool and per-complaint worker exclusion (R9, R10), transfers
refused while work is live (R15), and supervisors now notified on raise (R18).
