# 10. 51 of the 179 API operations have no frontend consumer

**Labels:** `api`, `frontend`, `inventory`
**Found:** 2026-08-11, by the end-to-end compatibility sweep
**Urgency:** Low as a defect, high as a planning input — it is the true remaining-work list

---

## Body

The service serves **179 operations**. The React app makes **124 API calls**, which between them
reach **120 operations**. The gap is 59, and it is not all one thing. Sorted:

| Bucket | Count | What it means |
|---|---|---|
| **Genuine — built, documented, nothing calls it** | **51** | the subject of this issue |
| Reached by something that is not a function call | 4 | see below; these are fine |
| A route that exists only as a legacy alias | 2 | `GET /auth/google/start`, `GET /auth/google/callback` |
| Infrastructure with no UI | 1 | `GET /health` |
| The sweep's own blind spot, declared | 1 | `GET /worker/unavailability` |

**The four reached another way**, and why no call-site scan can see them:

| Operation | Reached by |
|---|---|
| `GET /auth/oauth/{provider}/start` | `window.location.assign` — `frontend/src/store/authStore.js:31` |
| `GET /auth/oauth/{provider}/callback` | the identity provider redirecting the browser |
| `POST /auth/refresh` | a bare `fetch` inside the client itself — `lib/api/client.js:25` |
| `GET /dashboard/events` | `new EventSource(...)` — `lib/dashboard/dashboardApi.js:6` |

### The 51, by what is really missing

**23 + 1 — the resident portal.** Its own issue:
[9 — The resident portal is still a demo](09-resident-portal-is-still-a-demo.md). `GET /events` is
the `+ 1`: the audience-scoped stream `0028` was written for, whose only intended consumer is that
portal.

**27 — admin surfaces that were specified and not built.** These are not orphans; each has a screen
described in [`docs/design/ADMIN_DASHBOARD_DESIGN.md`](../design/ADMIN_DASHBOARD_DESIGN.md) that
does not exist yet, or exists in demo form over local state.

| Router | Count | Operations |
|---|---|---|
| `amenities.py` | 10 | `GET /amenities/{id}/bookings`, `…/approvals`, `…/ledger`, `…/ledger/summary`, `GET /amenity-reports`, `POST /amenities/{id}/bookings`, `POST /amenity-bookings/{id}/charges`, `…/damage`, `…/payments`, `…/refund` |
| `work_orders.py` | 8 | `GET`/`POST /complaints/{id}/work-orders`, `GET /departments/{id}/work-orders`, `GET`/`PATCH /work-orders/{id}`, `POST /work-orders/{id}/assign`, `…/cancel`, `…/reschedule` |
| `departments.py` | 5 | `GET /departments/{id}`, `POST`/`PUT /departments/{id}/staff`, `PATCH`/`DELETE /departments/{id}/staff/{staffId}` |
| `money.py` | 3 | `GET /billing-settings`, `POST /invoices`, `POST /invoices/{id}/payments` |
| `people.py` | 1 | `POST /admins` |

The `work_orders.py` block is the sharpest of these: it is the **supervisor's triage surface**, the
manual half of the dispatch engine. `0036`'s header states the rule the whole file is arranged
around — *every transition the engine will later make automatically is reachable by hand first* —
and the hand path currently has no screen. When the dispatcher misassigns a job, there is no
supported way to fix it.

The five `departments.py` operations are a different case again and worth checking before anyone
builds against them: the hiring flow that replaced them (`POST /departments/{id}/applications/…`,
`0035`) is wired and used, so some of these five may be **superseded rather than pending**. That is
a question for whoever owns the department surface, not an assumption this document should make.

## Why it matters

Unreached is not by itself a defect — an endpoint may legitimately land before its screen, and
several here did so deliberately. Three reasons it is worth writing down anyway:

1. **It is the only honest remaining-work list.** Every other artifact counts what is *built*.
   [`docs/API.md`](../API.md) §14 traces operations to user stories, and an operation with no
   consumer traces exactly as well as one with. This list is the difference between "the API serves
   this story" and "a person can do this".
2. **Unreached means unproven.** Nothing has verified that these responses are shaped the way a
   screen would need. Repository-mocked tests check the handler, not the contract as consumed.
3. **It decays quietly in the other direction too.** An endpoint deleted while a caller remains is
   caught by the same sweep, in its **call sites with no matching live route** section — which is
   empty today. Running it is cheap; the list only stays true if somebody does.

## How to confirm

```bash
cd backend && python scripts/frontend_api_sweep.py
```

The script's own docstring records how call sites are extracted, what it deliberately does not model,
and the one blind spot it declares rather than hides. Its numbers are the numbers in this document;
if they have drifted, this document is the thing that is stale.

Cross-reference an individual operation in [`docs/api_yaml_mapper.md`](../api_yaml_mapper.md) §3,
which gives its handler, line, `operationId` and the `API.md` section that documents it.

## Suggested fix

No code change. Two process ones:

- **Split it into real work items.** The 27 admin operations are three or four screens, not
  twenty-seven tasks; `work_orders.py` is the one to schedule first, for the reason above.
- **Re-run the sweep after any router or feature-module change** and correct this file, in the same
  spirit as `python scripts/export_openapi.py --check`. It is not wired into CI deliberately: the
  count is expected to move in both directions, and a gate that fails on a *falling* number would be
  a gate against building screens.

## Related

- [9 — The resident portal is still a demo](09-resident-portal-is-still-a-demo.md)
- [11 — snake_case in the published contract](11-snake-case-in-the-published-contract.md), the other
  finding from the same sweep
