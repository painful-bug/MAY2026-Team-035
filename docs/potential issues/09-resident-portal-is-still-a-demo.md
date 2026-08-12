# 9. The resident portal is still a demo, and 24 endpoints built for it have never been called

**Labels:** `frontend`, `resident`, `tech-debt`
**Found:** 2026-08-11, by the end-to-end compatibility sweep
**Urgency:** Before any demo that involves a resident, and before the resident backend is called done

---

## Body

The resident backend was built as a workstream of its own — migrations `0028`–`0033`, seven routers,
and a design document ([`docs/design/RESIDENT_BACKEND_DESIGN.md`](../design/RESIDENT_BACKEND_DESIGN.md))
that specifies each screen's data source. **Not one resident screen calls it.** Seven of the eight
pages in `frontend/src/pages/ResidentDashboard/` read from the zustand demo store
([`frontend/src/store/appStore.js`](../../frontend/src/store/appStore.js)) and nothing else.

| Page | Where its data comes from |
|---|---|
| `DashboardHome.jsx` | `useAppStore` |
| `Complaints.jsx` | `useAppStore` → `createComplaintsSlice.js` |
| `Visitors.jsx` | `useAppStore` → `createVisitorsSlice.js` |
| `Payments.jsx` | `useAppStore` → `createPaymentsSlice.js` |
| `Notices.jsx` | `useAppStore` → `createNoticesSlice.js` |
| `Profile.jsx` | `useAppStore` |
| `Faq.jsx` | static content, correctly |
| `Amenities.jsx` | `useAmenitiesStore` — a *second* local store, also seeded |

The store itself says what it is meant to be, at
[`appStore.js:15`](../../frontend/src/store/appStore.js):

> Browser state is a render cache only. Tenant records are hydrated from the backend snapshot and
> refreshed by the authenticated SSE stream; localStorage is deliberately never a source of domain
> truth.

Every clause of that is the intent and none of it is the behaviour. The slices mint their own ids,
and no resident page ever hydrates from `GET /api/v1/resident/snapshot`.

### The endpoints with no caller

Twenty-three resident operations, plus `GET /events` — the audience-scoped SSE stream that migration
`0028` exists for and that the sentence above describes:

| Router | Operations |
|---|---|
| `resident_snapshot.py` | `GET /resident/snapshot` |
| `resident_complaints.py` | `GET /complaints`, `GET /complaints/{id}`, `POST /complaints/{id}/read`, `POST /complaints/{id}/reopen`, `POST /complaints/{id}/resolution` |
| `resident_visitor_passes.py` | `GET`/`POST /visitor-passes`, `GET /visitor-passes/{id}`, `POST …/approve`, `…/reject`, `…/cancel` |
| `resident_money.py` | `GET /invoices/mine`, `GET /amenity-bookings/mine`, `POST /invoices/{id}/pay`, `POST /amenity-bookings/{id}/pay` |
| `resident_home.py` | `GET /notices`, `GET /me/household`, `POST /me/household/phones`, `GET /directory/contacts` |
| `resident_scheduling.py` | `GET /complaints/{id}/schedule-request`, `POST /complaints/{id}/schedule` |
| `resident_amenities.py` | `GET /amenities/available` |
| `events.py` | `GET /events` |

All twenty-four are documented in [`docs/API.md`](../API.md) §12 and present in
[`docs/openapi.yaml`](../openapi.yaml); [`docs/api_yaml_mapper.md`](../api_yaml_mapper.md) §3 gives
the handler and line for each.

## Why it matters

**This is not "a screen is missing".** The endpoints exist, are tested and are documented, so every
artifact in the repository reports the resident story as served — [`API.md`](../API.md) §14 traces
resident user stories to these operations, and the traceability table is what a reader checks. The
one thing nobody can do is use them.

Three specific costs:

1. **No response shape has ever been proven.** The defect class that only a consumer surfaces —
   a field named one thing by the schema and another by the screen — was found three separate times
   during Phase 1, each time on the day a real caller appeared. Twenty-four operations are carrying
   that risk unexamined. The demo slices cannot surface it, because they invent their own shapes.
2. **The demo actively contradicts the backend.** `createVisitorsSlice.js` implements a
   guard-raised approval request that the API deliberately does not have (the gap is recorded at
   `backend/app/api/v1/routers/resident_visitor_passes.py:134`). A reviewer watching the demo sees a
   feature; a reader of the API sees its absence documented. Both are looking at the current build.
3. **It hides which resident stories are actually deliverable.** See
   [`docs/product/USER_STORIES.md`](../product/USER_STORIES.md): the resident stories are marked
   served on the strength of the backend alone.

**This is not a regression and nobody hid it.** The resident workstream was explicitly backend-only,
and the demo frontend predates it. It is recorded here because the *combination* — a complete server
surface, a complete demo, and no wire between them — reads as a working feature from every angle
except the one that matters.

## How to confirm

```bash
cd backend && python scripts/frontend_api_sweep.py
```

Every operation listed above appears under **live operations no call site reaches**. Then, for the
other half of the claim:

```bash
grep -rl "lib/api/client\|features/" frontend/src/pages/ResidentDashboard/
```

Returns `Amenities.jsx` alone, and its imports are the local amenity store, not the API client.

## Suggested fix

The order matters more than the size. Wire `GET /resident/snapshot` **first** and let it fill
`DashboardHome`, exactly as `GET /worker/snapshot` fills the worker portal
(`frontend/src/pages/WorkerDashboard/Dashboard.jsx`) — one call, and its empty cases are the empty
states. That single step proves the session, the membership resolution, the cookie/CSRF seam and the
snapshot shape in one screen, and it is the step that will surface whatever is wrong.

Then one page at a time, react-query per page as the worker and security portals do, deleting each
demo slice as its last reader goes. `createVisitorsSlice.js` is last, because the security portal's
own migration away from it is already done and the resident screens are its only remaining readers.

**Do not** convert the slices to call the API from inside zustand. The house pattern, stated in the
service-operations journal §4.20, is react-query for anything the backend owns and zustand only for
UI state; a caching layer inside the store would be a second thing to invalidate.

## Related

- [10 — API operations with no frontend consumer](10-api-operations-with-no-frontend-consumer.md),
  the full inventory this is the largest single block of
- [4 — No migration has ever been applied to any database](README.md#4-no-migration-has-ever-been-applied-to-any-database),
  which is the other reason none of this has ever run
