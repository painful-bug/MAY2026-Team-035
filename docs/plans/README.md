# `docs/plans` — what we intend to build, and how far we got

Every document in here is **prospective**. It describes work that was intended,
in progress, or since completed — and it is written *before* the code, which is
the whole reason it exists and also the whole reason it goes stale.

That distinction is the point of the folder:

| Folder | Tense | If it disagrees with the code |
|---|---|---|
| [`../design/`](../design) | Why the built thing is built that way | The document is wrong; fix it |
| **`plans/`** | **What we were going to do** | **Neither is wrong — the plan is a record of intent** |
| [`../API.md`](../API.md), [`../openapi.yaml`](../openapi.yaml) | What the running app does | Generated; cannot drift |

**Never cite a document in this folder as evidence of what runs.** A plan that
was half-implemented, amended mid-flight, or abandoned still lives here at full
length, because the reasoning in it is what the next person needs. For what
actually exists, read the migrations and the generated spec.

---

## What is in here

| Document | Covers | Status |
|---|---|---|
| [`SERVICE_OPERATIONS_PLAN.md`](SERVICE_OPERATIONS_PLAN.md) | Service personnel, job dispatch and security operations — the current build | **In build.** Approved |
| [`SERVICE_OPERATIONS_PROGRESS.md`](SERVICE_OPERATIONS_PROGRESS.md) | The live work journal for the plan above — **written before each action, not after** | **Live.** Read this first to resume |
| [`BACKEND_PLAN.md`](BACKEND_PLAN.md) | The original backend derivation — schema, auth model, error contract | Largely built; §6 predates the OAuth decision |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | The first build order, and the "no bespoke API server" argument that was later overturned | Historical |
| [`ADMIN_DASHBOARD_PLAN.md`](ADMIN_DASHBOARD_PLAN.md) | What the admin frontend needs from the backend, screen by screen | Built |
| [`ADMIN_DASHBOARD_BUILD_PLAN.md`](ADMIN_DASHBOARD_BUILD_PLAN.md) | The step-by-step build order for the above | Complete |
| [`AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md`](AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md) | Auth and registration — **owned by the auth workstream, not by us** | Superseded as the architecture reference by [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| [`SCHEMA_RECONCILIATION_PLAN.md`](SCHEMA_RECONCILIATION_PLAN.md) | Rebuilding our migrations onto the merged baseline | Complete |
| [`RECONCILIATION_ADDENDUM.md`](RECONCILIATION_ADDENDUM.md) | Extends the above; does not replace it | Complete |
| [`REALTIME_AND_CACHING_STANDARD.md`](REALTIME_AND_CACHING_STANDARD.md) | The layering rule for client cache / SSE / server TTL cache / no-store HTTP, the SSE audience and topic rules, the one-`EventSource`-per-tab frontend, the scheduler non-interference rules, and the new-feature checklist | **Doctrine, standing.** Not a build record — read this before adding any read, mutable surface, or time-based feature |

---

## Conventions

- **A plan that is being executed carries a companion progress document.** The
  plan says what should happen; the progress document says what has. They are
  separate files because they decay at different rates — the plan is frozen once
  approved, the progress document is rewritten constantly.
- **Amendments are dated and in place.** When reality forces a change to an
  approved plan, the deviation is recorded in the progress document with the fact
  that forced it — the plan itself is not quietly rewritten to match what
  happened.
- **Moving or adding a document here means an entry in
  [`../CHANGE_LOG.md`](../CHANGE_LOG.md)**, per the rule in
  [`../design/README.md`](../design/README.md).
