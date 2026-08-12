# 12. Four notification parameters that no screen reads

**Labels:** `frontend`, `notifications`, `inventory`
**Found:** 2026-08-11, while fixing a fifth one
**Urgency:** Low each, but they share a failure mode with no alarm on it

---

## Body

Thirty-six notification `url` values across seven migrations carry a query
parameter, in ten distinct `(path, parameter)` pairs. On the morning this was
written **six of the ten were read by nothing**. Two were fixed the same day; the
four below are twenty-three of those thirty-six emissions.

The user taps a notification that says *"Your complaint has been assigned"*, lands
on the complaints screen, and is looking at a list. The one they were told about
is somewhere in it, unmarked. Nothing anywhere reports this: the link resolved,
the screen rendered, the API returned 200. It is the path-404 defect
[the link test](../../backend/tests/test_notification_links.py) was written for,
one step later and one degree quieter — a 404 at least sends the user somewhere
visibly wrong.

### The four still open

| Path | Parameter | Emitted by | Times | Screen | Whose |
|---|---|---|---|---|---|
| `/resident/complaints` | `complaint` | `0031`, `0036`, `0037`, `0039` | **11** | `ResidentComplaints` | see [9](09-resident-portal-is-still-a-demo.md) |
| `/admin/departments` | `job` | `0037`, `0039` | **7** | `AdminDepartments` | see [10](10-api-operations-with-no-frontend-consumer.md) |
| `/admin/complaints` | `complaint` | `0031` | **4** | `AdminComplaints` | the complaint-engine owner |
| `/admin/amenities` | `booking` | `0033` | **1** | `AdminAmenities` | the amenity author |

**They are not four instances of one bug.** Each needs a different answer, which
is why they are listed rather than batched:

* **`/resident/complaints?complaint=`** is the worst of the four by volume — eleven
  emissions, more than every other parameter combined — and the least fixable
  today, because the screen behind it reads a zustand demo store rather than the
  API. Reading the parameter would mean highlighting a row from seeded data that
  has no relationship to the complaint the notification is about. It is not a
  small fix waiting to be done; it is a symptom of issue 9, and it closes when
  that portal is wired.
* **`/admin/departments?job=`** has nothing to fix. There is no supervisor triage
  screen, so the parameter has no reader, not the wrong reader — the eight
  `work_orders.py` operations behind it have no frontend consumer at all
  (issue 10). `0036`'s header states the rule the file is arranged around: *every
  transition the engine will later make automatically is reachable by hand first*.
  The hand path is still unbuilt, and these seven notifications point at where it
  will go.
* **`/admin/complaints?complaint=`** belongs to the complaint-engine owner
  ([`../COMPLAINT_ENGINE_HANDOFF.md`](../COMPLAINT_ENGINE_HANDOFF.md)) and is the
  cheapest of the four: the screen is real, it lists real complaints, and it needs
  a `useSearchParams` read and a highlight.
* **`/admin/amenities?booking=`** is one emission, from the booking-payment
  notification in `0033`. The admin amenity screen predates it.

### The two that left, and what they cost to fix

Both on 2026-08-11, both in this workstream's own code, and worth recording
because they are what a fix actually looks like:

| Path | What was wrong | What it took |
|---|---|---|
| `/security/shifts?shift=` | the guard arrived at a fortnight of rows with the linked shift unmarked — and often not in the window at all, because `0045` schedules departures weeks out | a highlight, **plus a `shiftId` filter on `GET /security/shifts`**, because the 200-row cap makes widening the window unsafe |
| `/worker/messages?conversation=` | the thread the worker was notified about was selectable only by clicking; the open thread lived in `useState`, which cannot be linked to | moving the selection into `useSearchParams`, mirroring the admin twin that got it right, plus an error branch for an id that no longer resolves |

The first is the reason this list exists: fixing one and not counting the rest
would have left five of the same defect, each invisible for the same reason.

## Why it matters

An ignored parameter is not a broken link, and treating it as one would be wrong —
the user does reach a screen that can, in principle, show them what they came for.
What makes it worth writing down is that **there is no signal at all**. A broken
path is eventually noticed by a person who says "that took me to the home page".
An unread parameter produces a user who scrolls, does not find it, and assumes
they misread the notification.

## How to confirm

```bash
cd backend && python -m pytest tests/test_notification_links.py -q
```

`IGNORED_QUERY_PARAMETERS` in that file holds these four pairs and is asserted by
**equality**, not as a subset. So the list cannot grow quietly, and a screen that
starts honouring its parameter fails the suite until somebody removes it from the
record — which is the point: an improvement nobody notices is an improvement that
gets undone.

To see the full inventory rather than the exceptions:

```bash
cd backend && python -c "import sys; sys.path.insert(0, 'tests'); from test_notification_links import emitted_urls, query_parameters; print(*[(f, l, u) for f, l, u in emitted_urls() if query_parameters(u)], sep=chr(10))"
```

## Suggested fix

Three of the four are one screen change each, and all three are somebody else's
screen. In priority order, which is not the order of the table:

1. **`/admin/complaints?complaint=`** — real screen, real data, smallest change.
2. **`/admin/amenities?booking=`** — same shape, one emission.
3. **`/resident/complaints?complaint=`** — do it as part of issue 9, not before.
4. **`/admin/departments?job=`** — do it when the triage screen is built, as part
   of it. Nothing to fix in isolation.

## Related

- [9 — The resident portal is still a demo](09-resident-portal-is-still-a-demo.md)
- [10 — API operations with no frontend consumer](10-api-operations-with-no-frontend-consumer.md)
- [`../design/SECURITY_PORTAL_DESIGN.md`](../design/SECURITY_PORTAL_DESIGN.md),
  *The parameter, not just the path* — the fix that started the count
