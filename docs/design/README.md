# `docs/design` — the reasoning behind the backend

Every other document in `docs/` answers **what**. This folder answers **why**.

That split is deliberate, and it exists because the two kinds of knowledge decay
at completely different rates:

| Question | Where it is answered | How it survives |
|---|---|---|
| What does this endpoint return? | [`API.md`](../API.md), [`openapi.yaml`](../openapi.yaml) | Generated from the running app — it cannot drift |
| What tables exist? | `backend/supabase/migrations/*`, [`erd/`](../erd) | The migration *is* the schema |
| How is the process wired? | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Reviewed when the wiring changes |
| **Why is it built this way?** | **Here** | **Only if somebody writes it down** |

The first three regenerate themselves or fail loudly when they are wrong. The
fourth has no such safety net. Nobody's build breaks because a reason was lost —
the cost arrives six months later, when a constraint that took a week to arrive
at looks like an accident and gets tidied away by someone who had no way of
knowing better.

That is the specific failure these documents prevent. Concretely: the membership
lookup on every request (§2 of the admin document) looks like an obvious caching
opportunity right up until you know it is a revocation guarantee.

---

## What is in here

| Document | Covers | Status |
|---|---|---|
| [`ADMIN_DASHBOARD_DESIGN.md`](ADMIN_DASHBOARD_DESIGN.md) | The admin backend — layering, the authorization seam, the read/write split, migrations, the generated spec | **Built.** Written after the fact |
| [`RESIDENT_BACKEND_DESIGN.md`](RESIDENT_BACKEND_DESIGN.md) | The resident portal — endpoints, schema changes, live updates and push, the simulated payment gateway | **In build.** Written before the code; §9 says which steps have landed |
| [`SERVICE_OPERATIONS_DESIGN.md`](SERVICE_OPERATIONS_DESIGN.md) | Service personnel, job dispatch and gate/security operations — the third surface, and the first population that is not scoped to one community | **In build; the backend half is done.** The decision record lives in the plan; this is the coherence argument |
| [`SECURITY_PORTAL_DESIGN.md`](SECURITY_PORTAL_DESIGN.md) | The gate's two portals — the route map, the three notification URLs that are routing contracts, and the offline design with its threat reasoning | **Built.** Written after the fact; closes `US-3.5`, the last of the `US-3.x` set |
| [`AUTH_AND_SESSION_DESIGN.md`](AUTH_AND_SESSION_DESIGN.md) | Identity against membership — the `deps.py` seam, the one route resolver, the guards that ask for neither, and the notification substrate becoming person-addressed | **Built.** Written after the fact, at the PO's instruction, as the review packet for the auth workstream |

**One document in this folder is not a design document and is filed here
deliberately anyway.** [`../COMPLAINT_ENGINE_HANDOFF.md`](../COMPLAINT_ENGINE_HANDOFF.md)
sits at the top level of `docs/` rather than here, because it answers *what
somebody else has to decide* rather than *why this is built this way*. It exists
because building the service surface on top of the complaint path produced seven
questions that cannot be answered from inside it — each is about what a complaint
means or when it ends. If you are reading `SERVICE_OPERATIONS_DESIGN.md` §4.4 and
wondering who rules on auto-resolution, that is the file.

Read the admin document first. It establishes the paradigms; the resident and
service documents say *"as in the admin backend"* and do not repeat the
reasoning.

**`AUTH_AND_SESSION_DESIGN.md` cuts across all three** rather than describing a
fourth surface, which is why it is not in the "read in order" list. It exists
because the auth seam is shared between workstreams and the service-operations
build had to change it; the PO's condition for allowing that was that the change
be written up in detail rather than left as a diff. Read it when you are touching
`deps.py`, `authService.js`, `authRoutes.js`, or anything that decides who a
notification is for.

**Where the decisions live.** A design document here answers *why the built thing
is built that way*. What we **intended** to build lives in
[`../plans/`](../plans) — including, for the service surface, the full decision
record `D1`–`D15` with each rejected alternative. `SERVICE_OPERATIONS_DESIGN.md`
therefore cites that plan rather than restating it, and confines itself to the
part the plan does not cover: how the new surface stays coherent with the two
that already exist.

**Four are retrospective and one is prospective, and that difference matters when
you read them.** The admin, security-portal and auth documents describe code you
can go and check — if one and the code disagree, the code wins and the document
is a bug; the service-operations document is retrospective for its backend half.
The resident document describes an intention, and its open questions in §8 are
genuinely open. Do not cite any of them as evidence of what runs in production.
For that, read the migrations and the generated spec — and note that **no
migration in this repository has been applied anywhere yet**, so "built" here
means the code and the SQL exist and are verified statically.

---

## How to read one

All five follow the same shape, and it is worth knowing which section you want:

1. **How the requirement was derived** — and why that method, since the source
   was never a written spec.
2. **Findings** — things discovered about the existing system that changed the
   design. These are the highest-value paragraphs in either document.
3. **Design decisions** — each one states the decision, the reasoning, and
   **the alternative that was rejected and why.**
4. **The mechanism in detail** — for anything a reader could not reconstruct
   from the code alone.
5. **Open questions** — with a default recorded for each, so an unanswered
   question does not block the work.
6. **A coherence checklist** — every paradigm the design preserves, so
   divergence is visible rather than gradual.

**The rejected alternatives are not padding.** They are the part that stops the
same debate being had again in nine months, and they are the reason a reviewer
can tell "we chose A" from "we never thought about B".

---

## Conventions

- **State the cost.** Any decision with a real downside says so under a heading
  that admits it — *"Cost, stated honestly"*. A design document that lists only
  benefits is marketing, and it teaches the reader not to trust the rest of it.
- **Cite `file:line` for claims about existing code.** A reader must be able to
  check without hunting. If a citation goes stale, that is a signal worth having.
- **Corrections stay visible.** When something in one of these documents turns
  out to be wrong, it is corrected *in place with a note saying what it replaced*
  — not silently overwritten. The reasoning that led somewhere wrong is often the
  most useful thing on the page, because the next person is liable to reason the
  same way. See §3.5 of the resident document for a worked example.
- **Separate what is decided from what is defaulted.** A default that nobody has
  ruled on is marked as such and lives in the open-questions section.
- **Every change is logged.** Adding or amending a document here means an entry
  in [`CHANGE_LOG.md`](../CHANGE_LOG.md), attributed `PO` (a product-owner
  ruling), `DERIVED` (a consequence of one) or `AUDIT` (found by comparing
  artifacts against each other). A ruling that overturns something already
  written says so explicitly, and says what it overturned.

---

## Adding a document

One per **component**, not one per feature — a component being something with
its own surface, its own service layer and its own reason to exist. ~~Two
documents today; a third would be justified by, say, the gate/security surface
if it ever gets an owner.~~ **Five today, and that sentence is left visible
because the gate did get an owner** — `SECURITY_PORTAL_DESIGN.md` is the document
it was predicting, written on 2026-08-11 when the portal was built. The count is
a poor rule anyway; the test is the definition above it.

Before writing one, check the five artifacts every proposal here is checked
against, because a design that contradicts one of them is not finished:

1. the frontend ([`FRONTEND_CHANGES.md`](../FRONTEND_CHANGES.md) and the live
   source under `frontend/src`),
2. the ERD ([`erd/`](../erd)),
3. the class diagram ([`class-diagram/`](../class-diagram)),
4. the component design ([`design-of-components.md`](../design-of-components.md)),
5. the Supabase schema (`backend/supabase/migrations/`).

Then trace every proposed endpoint to a user story in
[`product/USER_STORIES.md`](../product/USER_STORIES.md), or type it explicitly as
serving none. [`API.md` §16](../API.md#16-user-stories--endpoints) is where that
matrix lives, and `backend/scripts/api_annotations.py` is what puts it in the
spec. *(This said §15 until 2026-08-11; §15 has been "Not yet implemented" since
the resident backend renumbered the sections behind it — the same stale
cross-reference `USER_STORIES.md` carried for US-3.2 and corrected a day
earlier.)*
