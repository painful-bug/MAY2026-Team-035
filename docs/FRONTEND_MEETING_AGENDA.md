# Frontend team — meeting agenda

**Date raised:** 2026-07-29
**From:** backend, while planning the admin dashboard
**Purpose:** seventeen things the backend cannot resolve on its own. Everything else has been absorbed
by the API layer and needs no frontend change.

**Items 8, 13, 15 and ~~17~~ are live bugs** (17 closed 2026-08-12). The rest are design mismatches. Items 9 and 10 were added
while building the departments endpoints and items 11 to 13 while building the money endpoints
(2026-07-29); **items 14 to 16 while building the amenity endpoints, and item 17 while building the
settings endpoints** (2026-07-30).

**Item 12 was the largest single gap in the product**, and it was not a mismatch: there was no screen
that could bill anybody. *(Three of its four bullets closed 2026-08-12 — an invoice can be raised, an
offline payment recorded and the rate configured; the recurring monthly cycle is still nobody's. Item
17 closed the same day; items 8, 13 and 15 were not re-checked in that pass.)* **Item 14 is the largest open
question**: there appear to be two unrelated
amenity products in the codebase, and we can only serve one of them. **Item 17 is the one where your
answer changes our field names**, so it is worth ten minutes now rather than after something depends
on them.

**Ground rule we are working under:** we do not change `frontend/src/`. The backend matches the
frontend's existing shapes wherever that is possible — including `timeAgo`, display-string joins and
the free-text assignee. The seventeen items below are the cases where matching is either impossible or
costs something worth knowing about.

Each item states **what the frontend does today**, **why it is a problem**, and **what we would need**
— with the cost of doing nothing, because doing nothing is a legitimate answer for several of these.

---

## 1. Free-text complaint assignee *(blocks nothing; degrades everything)*

**Today:** [`Complaints.jsx:175`](../frontend/src/pages/AdminDashboard/Complaints.jsx) is a plain text
input. An admin types anything into `assignee`. [`DepartmentDetail.jsx:193`](../frontend/src/pages/AdminDashboard/DepartmentDetail.jsx)
sets it to `` `${staffMember.name} - ${staffMember.role}` ``, and line 217 parses the name back out
with `assignee.split(' - ')[0]`.

**Problem:** we cannot store a foreign key to a person who was typed rather than chosen. So
"complaints assigned to me", staff workload, and any staff-facing dashboard cannot be built — there is
nothing to filter on. A typo silently creates a new "person".

**Ask:** make the assignee a **select over department staff**. Small change, one screen.

**If not:** we store `assignee_label` as text with a nullable FK. The dashboard keeps working exactly
as it does now, and every by-assignee feature stays impossible.

---

## 2. One complaint category, two departments *(needs a product answer)*

**Today:** [`Departments.jsx:211`](../frontend/src/pages/AdminDashboard/Departments.jsx) is a
multi-select, and nothing stops two departments both selecting "Plumbing".
`createDepartmentsSlice.js:151` then shows the complaint under both.

**Problem:** the category is what routes a complaint to a department *and* what supplies its SLA. With
two owners, **"which department's SLA applies?" has no answer** — and the SLA determines whether a
complaint is breaching. This is a product question, not a schema detail.

**Ask:** confirm whether a category may genuinely have two owning departments.
- If **no** — disable categories another department already claims. Simpler schema, unambiguous routing.
- If **yes** — we need a rule for which SLA wins.

**Interim:** we build the join table, and the **lowest `sla_hours` wins**. That is a workaround, not
an answer.

---

## 3. Pre-formatted dates make responses un-cacheable *(a real cost, quietly)*

**Today:** `complaints[].timeAgo` is `"2h ago"`, `notices[].date` is `"July 8, 2026"`, rendered
directly.

**Problem:** to keep these working the server must format them, which means **every response
containing one can never be cached** — no CDN, `Cache-Control: no-store` — because a cached `"2h ago"`
is wrong the moment it is served. It also puts the server's clock and locale into a value that is
properly the browser's.

**Ask:** format relative times client-side. We will send ISO-8601 instants in the same payload from
day one (`submittedAt` beside `timeAgo`), so this can be adopted one screen at a time whenever suits.

**If not:** it works, it is just slower and more expensive than it needs to be, forever.

---

## 4. Labels used as foreign keys

**Today:** `apartmentId` is `` `${tower}-${flatNumber}` ``; `complaints[].flat` is `"B-1204"`;
`departments[].head` is `"Ramesh Kumar"`; `payments[].tower` is `"B"`.

**Problem:** renaming a block breaks every row that referenced it by name, and two people with the
same name are indistinguishable.

**Ask:** nothing urgent. We send the id alongside the label on every entity (`unitId` beside `flat`,
`headMembershipId` beside `head`). Extra keys are ignored, so **nothing breaks today** — adopt them
whenever a screen is being touched anyway.

---

## 5. One invite for a whole flat, or one per phone?

**Today:** "Add Resident" creates **one user record per phone number** for a flat, then mints **one
invite token** covering all of them; redeeming it activates every user of that `apartmentId`.

**Problem:** the ERD is built the other way — one invitation redeems into one membership. Neither is
wrong, but they cannot both be true, and this decides what "Add Resident" returns.

**Ask:** confirm the intended behaviour. **We suggest one invite per phone**, grouped in the response
so the UI can still present them together — one person redeeming should not activate their
neighbours' accounts, and today it does.

---

## 6. Onboarding promises module editing that does not exist *(the backend half now exists — 2026-07-30)*

**Today:** [`FeatureConfigurationPage.jsx:79`](../frontend/src/pages/FeatureConfiguration/FeatureConfigurationPage.jsx)
tells the founder these features *"can be changed later from the Admin Settings page."* No such control
exists on that page.

**Problem:** a visible broken promise on day one. And it goes further than the missing control:
**`enabledModules` is read only inside the onboarding flow that writes it.** The five files that
mention it are all onboarding — the wizard, its slice, its service, its store and the success page.
No admin screen, route or layout consults it: [`AdminLayout.jsx:32-43`](../frontend/src/layouts/AdminLayout.jsx)
is a fixed ten-item nav array. So the choice the founder makes during onboarding changes nothing
anywhere after the wizard finishes, before or after they try to edit it.

**Ask:** a module toggle list on Settings, calling `GET /settings/modules` and
`PATCH /settings/modules/{moduleKey}`.

**We have already absorbed it:** as of build step 9 the endpoints exist — a ten-row catalogue with
labels, descriptions, defaults and per-module state, plus a bulk `PUT /settings/modules` taking the
same `enabledModules` array shape the onboarding wizard already produces. **This is now the only item on
the list where the backend is finished and the frontend half is untouched.**

**One field worth rendering:** each module carries a `backendStatus` of `implemented`, `partial` or
`none`, and **six of the ten are `none`**. Without showing it, an admin can switch on Parking
Management and be given no hint that nothing will happen.

**Not yet decided, and yours to weigh in on:** turning a module off does not currently `403` anything or
hide any navigation — it records a preference. Enforcing it would `403` all twenty-two amenity endpoints
on every existing community, because `amenities-booking` ships disabled in `onboardingModules.js`. That
is `DECISIONS_NEEDED.md` A24.

---

## 7. The dashboard has never rendered an empty state

**Today:** every count derives from seeded arrays, so there is always data.

**Problem:** a real newly founded community has **zero** residents, complaints, payments and
activity — dividing by zero for the collection percentage, empty charts, blank tables with no
explanation. **This is the first screen a real founding admin sees**, and it is the one screen never
tested.

**Ask:** an empty rendering for each list and each dashboard tile.

**We will help:** every list endpoint returns `{ items: [], total: 0 }` rather than 404, with an
identical envelope whether or not there is data, so there is one shape to design against.

---

## 8. A live bug: approving a seeded registration produces `C-C-505` *(found 2026-07-29)*

**Today:** [`createPendingRequestsSlice.js:36`](../frontend/src/store/slices/createPendingRequestsSlice.js)
builds the flat as `` `${request.tower}-${request.flat}` ``. That is right when the request came from
the registration form, where `addPendingRequest` sets `flat: formData.flatNumber` — a bare `505`,
giving `C-505`. But the seeded requests in `data/pendingRequests.js` already store `flat: 'C-505'`.

> **Overtaken 2026-08-11.** `data/pendingRequests.js` was deleted in `94556e5`, when the pending
> registrations screen started reading the API instead of seed data, so the second of the two code
> paths is gone and the collision cannot occur. The item is left in place because the *disagreement*
> it describes — whether `flat` holds a bare number or a full code — is a real question about the
> field, and `createPendingRequestsSlice.js:36` still builds the value by joining. `app/domain/units.py`
> still normalises both shapes on our side.

**So approving a seeded request creates a resident in flat `C-C-505`** — a flat that does not exist
and never will. Two code paths disagree about whether `flat` holds a number or a full code.

**Problem:** in the demo this is invisible, because nothing validates the flat. Against a real
backend it silently creates a junk unit on first reference, and that resident is then permanently
attached to a flat nobody lives in.

**Ask:** pick one meaning for `flat` and use it in both places. We suggest the full code everywhere,
since that is what every other screen renders.

**We have already absorbed it:** the API normalises both shapes to one canonical code
(`app/domain/units.py`), so nothing breaks today whichever way you decide. Raising it because the
frontend will keep producing the wrong value in its own state until it is fixed, and because the next
person to write this expression will get it wrong the same way.

---

## 9. Two department-create screens disagree about what a category is *(found 2026-07-29)*

**Today:** there are two ways to create a department, and they model categories differently.

- [`Departments.jsx:22`](../frontend/src/pages/AdminDashboard/Departments.jsx) offers a **fixed
  checkbox list of six** — Plumbing, Electrical, Infrastructure, Cleaning, Security, Others.
- `CreateDepartment.jsx:79` is a **free-text box**, and its placeholder is *"e.g. Leaking pipes"* —
  which is a symptom, not a category. A department created there can claim categories no complaint
  will ever carry, because `raiseComplaint` picks from the fixed list.

> **Resolved 2026-08-11.** There is now one department-create path, not two: `CreateDepartment.jsx`
> was deleted when the department screens were wired to `POST /departments`, and the fixed list in
> `Departments.jsx` is the only way in. **The third disagreement below is not resolved**: department
> categories are claimed by name and the API does not hold a closed list of them
> (`departments_service.py:237`), so `Others` is still a category a department can claim and no
> complaint carries. That is the half of this item still worth ten minutes.

There is a third disagreement underneath: the seeded vocabulary has **five** categories. `Others` is
in the checkbox list and in neither the seed data nor any complaint.

**Why it matters:** categories are what route a complaint to a department and what decide its
deadline. A category nobody can select is a department that receives nothing, silently.

**What we need:** one answer to "is the category list controlled or open?", and both screens
following it.

**We have already absorbed it:** category names are **upserted** on department save, so both screens
work today. The cost is that a typo becomes a permanent new category, and that
`GET /complaint-categories` will slowly fill with symptoms.

## 10. `head` is free text that is not connected to `staff[]`

**Today:** `departments[].head` is a plain string. In the seed data it always also appears in
`staff[]` — dept-plumbing's head *Ramesh Kumar* is `staff[0]` — but nothing enforces that, and the
edit form lets you type a name belonging to nobody.

**Why it matters:** the head is who a complaint escalates to. A name that matches no roster entry has
no phone number and no workload.

**What we need:** make the head a select over the department's own staff. Small change, and it makes
the field mean something.

**We have already absorbed it:** naming a head promotes the matching roster row to `rank = 'head'`
(demoting the incumbent in the same transaction), and creates a roster entry when nothing matches. So
the field round-trips exactly and there is always a real person behind it — invented, if necessary.

---

## 11. The money tiles are computed in the browser, so paging will break them *(found 2026-07-29)*

**Today:** [`Maintenance.jsx:11-17`](../frontend/src/pages/AdminDashboard/Maintenance.jsx) computes
"Total Collections Received", "Outstanding Receivables", "Total Billed Dues" and the collection
efficiency percentage by summing the whole `payments` array in the browser.
[`AdminHome.jsx:25-29`](../frontend/src/pages/AdminDashboard/AdminHome.jsx) does the same for its
collection card.

**Why it matters:** that is correct only while every invoice fits in one response. A community with
600 flats billed monthly produces 7,200 invoices a year — the table has to page, and the moment it
does, **the tiles above it silently report the total of one page**. Not an error, not an empty
state: a smaller number, in rupees, that looks entirely plausible.

This is the same class of problem as the counts on the home page, but it is worse in one specific
way: nobody double-checks a resident count, and everybody double-checks a money total — against a
bank statement, a month later.

There is a second, smaller version of it already live. A partially paid invoice keeps its **full**
`amount` (the column is headed "Amount"), so summing `amount` over `Unpaid` rows overstates
receivables by whatever has already been paid.

**Ask:** read the three tiles from **`GET /api/v1/invoices/summary`** rather than summing rows. One
request, and it returns the figures already computed.

**We have already absorbed it:** the endpoint exists, aggregates in Postgres over every invoice in
the community, sums outstanding **balances** rather than invoice amounts, and excludes voided
invoices. Nothing breaks today — it is simply available and unused.

---

## 12. There is no way to bill anybody *(found 2026-07-29 — the biggest gap we have found)* — ◐ three of four closed 2026-08-12

> **Closed by the phase-7 money wiring, except the recurring cycle.** `Maintenance.jsx:46` calls
> `moneyApi.createInvoice` (`POST /invoices`) and `:201` calls `moneyApi.recordPayment`
> (`POST /invoices/{id}/payments`), so an invoice can be raised and an offline payment recorded from
> a screen; `Settings.jsx:137-144` writes `defaultMaintenanceAmount` through
> `PUT /billing-settings`, so the rate is a choice rather than a constant. **The third bullet is
> still open** — nothing runs a monthly maintenance cycle, because `POST /maintenance-runs` was
> removed by the wiring audit and nothing schedules anything (`DECISIONS_NEEDED.md` A22). The
> hardcoded `4250` in `createPendingRequestsSlice.js:43` also survives, in the demo approval handler.
>
> The description below is left as raised, per this file's convention.

**Today (2026-07-29):** the Maintenance screen lists invoices and shows three tiles. That is all of
it. There is **no screen** that:

- creates an invoice,
- records a payment that arrived by cash or cheque,
- runs a monthly maintenance billing cycle,
- or sets the maintenance amount.

The only place an invoice is ever created is
[`createPendingRequestsSlice.js`](../frontend/src/store/slices/createPendingRequestsSlice.js), inside
the *approval handler*, with a hardcoded `4250` and a hardcoded title of `"Maintenance Fee - July
2026"`.

**Why it matters:** the demo works because `data/payments.js` is seeded. A real community starts with
zero invoices and has no way to create the first one, so the collections screen reports on an empty
table forever. **This is the one screen where "it works in the demo" and "it works" are furthest
apart.**

The maintenance amount is the sharpest edge of it: `4250` is a demo constant sitting in the middle
of an approval handler, and nothing in the product — not a settings screen, not the ERD — says what a
real community's rate is or where it would live.

**Ask:** three screens, in this order of value.
1. **Billing settings** — the maintenance amount, the due day, the invoice prefix. Smallest, and
   unblocks the other two.
2. **Run monthly billing** — one button, one confirmation, "42 flats invoiced".
3. **Issue a one-off invoice** and **record an offline payment** — the clubhouse-charge case, and the
   resident who pays in cash.

**We have already absorbed what we can:** `POST /invoices`, `POST /maintenance-runs`,
`POST /invoices/{id}/payments`, `POST /invoices/{id}/void` and `GET`/`PUT /billing-settings` all
exist and are documented in `API.md` §9. The billing run is safe to double-click — a partial unique
index makes a second run for the same period bill nobody. And a run with no amount configured is
**refused** rather than falling back to `4250`, because adopting a demo constant would bill a real
community a number nobody chose.

---

## 13. A small live bug: residents see literal asterisks on their payment method

**Today:** [`Payments.jsx:113`](../frontend/src/pages/ResidentDashboard/Payments.jsx) renders
`<span>Method: **{inv.paymentMethod}**</span>`.

**Problem:** that is JSX, not markdown. The asterisks are printed. A resident's payment history reads
`Method: **UPI**`.

**Ask:** drop the asterisks, or wrap the value in `<strong>`. One line.

**Nothing to absorb:** we send the method exactly as your seed data spells it — `UPI`, `Net Banking`,
`Credit Card` — so the value is right and only the wrapper is wrong. Raising it because it is on a
screen residents see every month.

---

## 14. There appear to be two unrelated amenity products *(found 2026-07-30 — the largest open question)*

**Today:** there are two amenity models in `frontend/src/`, and nothing connects them.

| | `features/amenities/` | `data/amenities.js` + `store/slices/createAmenitiesSlice.js` |
|---|---|---|
| Ids | `amenity-gym` | `a1` |
| Hours | `openingTime: '06:00'` + a settings object | `timing: '06:00 AM - 10:00 PM'` |
| Status | `Active` / `Inactive` | `Available` / `Bookable` / `Open` / `Under Maintenance` |
| A booking's time | `startTime: '07:00'`, `endTime: '09:00'` | `timeSlot: '07:00 AM - 08:30 AM'` |
| Size | 114 files: catalogue, four-tab workspace, ledger, reports | 3 files |

[`ResidentDashboard/Amenities.jsx`](../frontend/src/pages/ResidentDashboard/Amenities.jsx) reads the
first. [`ResidentLandingPage.jsx`](../frontend/src/pages/ResidentLanding/ResidentLandingPage.jsx)
reads the second. Both are live.

**Why it matters:** an amenity cannot have both `timing: '06:00 AM - 10:00 PM'` with
`status: 'Bookable'` **and** a five-group settings object with opening hours, a booking mode and a
capacity. **No backend can serve both shapes at once**, so this is not a mismatch we can absorb — it
is a choice somebody has to make.

We built the first, because it is the one the admin dashboard uses and the one the ERD describes.
The second has no ERD counterpart at all.

**Ask:** confirm the `features/amenities` model is the real one, and say what happens to the landing
page — retire it, or point it at the same endpoints.

**We have already absorbed what we can:** nothing, on this one. It is the one item on this list where
"we handled it" is not available.

---

## 15. The cleaning buffer makes shared capacity unreachable *(found 2026-07-30 — a live bug)*

**Today:** [`amenityBookingsService.js:322-341`](../frontend/src/features/amenities/services/amenityBookingsService.js)
rejects any proposed booking that overlaps a cleaning buffer — **in shared mode as well as
exclusive**. [`amenityTimeline.js`](../frontend/src/features/amenities/utils/amenityTimeline.js)
paints a buffer after every booking.

**Problem:** follow it through on the seeded gym — mode `Shared`, capacity **24**, buffer 15 minutes.

1. Anita books 07:00–09:00.
2. A buffer appears at 09:00–09:15.
3. Vikram asks for 07:30–09:30. It overlaps the buffer, so it is refused.
4. So is every other overlapping request, for any duration.

**A shared amenity with a non-zero cleaning buffer accepts exactly one booking at a time.** Its
capacity of 24 is a number nothing can ever reach. The seed data hides this completely: no two gym
bookings overlap, so the bug never fires in the demo.

**Ask:** decide what the buffer means. Our reading is that it is time to clean the facility *between
uses*, which only exists when somebody has vacated it — so it should not apply between two people
sharing the gym at once.

**We have already absorbed it, and this one changes behaviour:** the backend applies the buffer only
between uses that occupy the amenity **exclusively** — exclusive-mode amenities, and private bookings
on hybrid ones. Between two shared bookings, capacity governs. **This means the API will accept
bookings the demo refuses**, which is why it is on this list rather than in a commit message.
`DECISIONS_NEEDED.md` A18 is the same question in the form of an answer box.

---

## 16. The approvals table cannot say how many days a request covers *(found 2026-07-30)* — ✅ closed 2026-08-12

> Closed by the phase-7b amenity wiring: `ApprovalRow` renders `dayCount` and the detail shows
> `dates`, and the same change fixed a live bug nobody had listed — the demo was posting the
> **occurrence** id to `POST /amenity-bookings/{seriesId}/approve`, so approving one row of a
> three-day request was approving a different thing than the API understood. Original text kept
> below for the record.

**Today:** [`createResidentAmenityBookingSeries`](../frontend/src/features/amenities/services/amenityBookingsService.js)
creates one booking record per date, sharing a `bookingGroupId`. `approveAmenityBookingRequest`
approves exactly one of them, and [`ApprovalTable.jsx`](../frontend/src/features/amenities/components/Approvals/ApprovalTable.jsx)
renders one row per record.

**Problem:** a resident asking for the hall on three consecutive days appears in the approvals table
three times. An admin can approve Monday, reject Tuesday and never notice Wednesday — which is not a
decision anybody meant to make, and leaves a resident with a two-thirds event.

**Ask:** render `dayCount` on the approval row, and `dates` in the detail. Two fields, already sent.

**We have already absorbed it:** `GET /amenities/{id}/approvals` returns **one row per request**
carrying its first day, `dayCount` and the full `dates` array, and one `POST .../approve` decides all
of them. That is the behaviour an admin expects from a button labelled "Approve" — but **a row that
shows only the first day while approving three is misleading**, so the field needs rendering. Until
it is, the row is honest about its date and quiet about its scope.

---

## 17. The Settings screen tells admins it saved, and saves nothing *(found 2026-07-30 — a live bug, and the one where your answer changes our field names)* — ✅ closed 2026-08-12

> **The save button is no longer a lie.** [`Settings.jsx`](../frontend/src/pages/AdminDashboard/Settings.jsx)
> is 389 lines and its `handleSave` (`:93`) writes both endpoints this item names: `PUT /settings`
> for `requireVisitorPreapproval` and `noticeSmsBroadcastEnabled` (`:130-131`) and
> `PUT /billing-settings` for the money pair and the amounts behind them (`:137-144`), reading them
> back at `:62-63` and `:75-81`. **Ask 1 was never answered**, so the four field names in the table
> below are still ours by default rather than by agreement — which is the part of this item that is
> closed by shipping rather than by deciding, and the distinction is worth keeping.
>
> The description below is left as raised, per this file's convention.

**Today (2026-07-30):** [`Settings.jsx`](../frontend/src/pages/AdminDashboard/Settings.jsx) is 135
lines. Four `useState` toggles, and:

```js
const handleSave = () => {
  showToast('Admin Settings Saved Successfully', 'success');
};
```

No store slice, no service module, no `persist` entry. An admin flips four switches, is shown a green
toast that says *"Admin Settings Saved Successfully"*, and loses all four on reload. Everything else in
this product persists — this is the only screen whose save button is a lie, and the toast is what makes
it a bug rather than a gap: without it, an admin would notice.

**Why it matters to us more than the other sixteen items:** every other section of `API.md` reproduces
a shape your code already has. **Here there was nothing to match, so the field names are ours.** We
chose them to say what your own labels say, but they are the one part of the contract you had no vote in:

| Your label | Our field | Lives at |
|---|---|---|
| Automated Monthly Maintenance | `autoBillingEnabled` | `PUT /billing-settings` |
| Late Payment Fine Charges | `lateFeeEnabled` (+ `lateFeeAmount`, `lateFeeGraceDays`, `lateFeePeriod`) | `PUT /billing-settings` |
| Gate Security App Pre-approvals | `requireVisitorPreapproval` | `PUT /settings` |
| Urgent Notice SMS Broadcast | `noticeSmsBroadcastEnabled` | `PUT /settings` |

**Note the two different endpoints.** Two of your four switches are money, and money already had a home
and a writer from build step 7. One `GET /settings` returns all four so the card renders in a single
request; the billing pair is read-only there and written at `PUT /billing-settings`, because two writers
is how one rate starts disagreeing with itself.

**Ask, in order of how much it costs you:**

1. **Tell us if any of these four names is wrong.** Now is free; later is a migration and a breaking
   change on both sides.
2. **Wire the four toggles up.** `GET /settings` gives you everything the card needs in one request.
3. **Read `hasSavedSettings`.** A community that has never saved gets a full `200` with every value
   populated — `Asia/Kolkata`, 72 hours, `Flat`. Those are *defaults, not choices*, and a screen that
   renders them identically tells an admin they picked a timezone they have never seen. Same for
   `unitLabelIsDerived` on the one field where the label is inferred from the community type.

**Two of the four are stored and read by nothing, and you should know which:** there is no visitor table
or endpoint anywhere in the backend, and no SMS provider in the repository. `requireVisitorPreapproval`
and `noticeSmsBroadcastEnabled` are a stored policy waiting for a feature. We store them because the
screen currently *loses* them, which is worse — but a tooltip promising SMS goes out tonight would be
wrong. Likewise **nothing runs billing on a schedule and nothing charges a late fee**
(`DECISIONS_NEEDED.md` A22, A23).

**One behaviour that will surprise you if you do not expect it:** a toggle cannot be switched on without
the number it acts on. `autoBillingEnabled: true` while `defaultMaintenanceAmount` is null is a `409`,
and so is `lateFeeEnabled: true` without a `lateFeeAmount` above zero — send both in one request and it
succeeds. We chose a `409` over silently ignoring the key because ignoring it would return `200` and let
the toggle spring back on the next read, which is the bug this screen already has in a different form.

**`lateFeeAmount` starts null, deliberately.** Your copy mentions ₹100; we did not adopt it as a default.
A number nobody chose is indistinguishable from one they did, and this product already has one of those
(the hardcoded `4250` — item 12).

---

## 18. *Show QR* will stop working unless the client keeps the code *(found 2026-08-04 — not a bug, a consequence)*

**What the screen does now.** `Visitors.jsx` rebuilds the QR payload from the visitor in the store
every time somebody taps *Show QR*, and `copySecurityCode` reads the six digits back off the same
object. That works because the prototype keeps both in the browser for ever.

**What the API does.** The security code and the QR token are returned by `POST /visitor-passes` and
by nothing else, ever. They are stored as hashes — the plaintext is not even sent to the database —
so there is no read that can return them and no support procedure that can recover them. This is
`RESIDENT_BACKEND_DESIGN.md` §5.4, and it is the same rule the resident invite already follows.

**What that means for you.** The `201` is the only time you will see either value. If you want *Show
QR* to keep working, store what it hands you against the pass id for the life of the pass. Clearing
storage or signing in on a second device loses the QR — **not the pass**: it is still live, and the
six digits still open the gate for anyone who wrote them down.

**What we need from you.** Whether losing the QR on a new device is acceptable. If it is not, the
shape that keeps the rule is a `POST /visitor-passes/{passId}/code` that mints a **fresh** code and
invalidates the old one — a reissue, not a recovery. We have not built it, because issuing a new pass
already does the same job with one more row. Your call.

**Two smaller things on the same screen**, neither of which needs an answer:

- The form has no visitor **name** field, and `visitor_name` is required in the database, so
  `createVisitorsSlice.js` composes *"Guest group"*. `visitorName` is therefore **optional** on our
  endpoint and we compose the same label from the same rule when you omit it. Send one if you ever
  add the field.
- Your history tab uses `['Checked Out', 'Rejected'].includes(status) || date < today`. We return
  `isCurrent` as a computed field so the two tabs are one server-side rule — and we matched your
  behaviour on the case that matters: a **checked-in** guest stays on the *current* tab, whatever
  their window says.

---

## 19. The home screen is one call now, and three of its numbers are not what the store computes *(found 2026-08-04 — no answer needed, but read it before wiring)*

`GET /resident/snapshot` returns everything `DashboardHome.jsx` renders. Three of its figures were
derived from your code rather than from our design, and they are worth knowing because they are the
ones that would silently differ if you kept computing them locally.

- **`visitors.expectedGuests` and `checkedInGuests` are guests, not passes.** We reduce over
  `guestCount` exactly as you do. One pass for a party of twelve counts as twelve. `Expected` and
  `Approved` are counted **together**, again as you do — to a resident they are one thing, somebody
  who has not arrived yet.
- **`dues.primaryInvoice` is the maintenance bill, or else the *oldest* payable one.** You take
  `unpaidInvoices[0]`. Ours differs only when there is no maintenance bill, and it differs on
  purpose: offering the newest would hide an overdue bill behind a fresh one. It is a whole invoice
  object, so the Pay button on the home screen is drawn from the same `isPayable` as the one on the
  Payments page.
- **`unreadNotifications` counts the whole feed, not the five events in `activity`.** Draw the badge
  from it. A badge counted from a page is wrong as soon as anyone scrolls.

One field to handle rather than ignore: **`dues.isPartialTotal`**. It is `false` for any resident
with a normal number of unpaid bills, and `true` means `outstandingTotal` is a floor rather than a
total because there were more bills than one read carries. If it is ever true, send them to Payments
rather than showing the sum as if it were everything.

Finally, **`activity` is the notification feed** — the same rows `GET /notifications` pages through,
newest five. There is no separate activity log, so a click can route straight to `url` and marking
one read is the notifications endpoint you already have.

---

## Not on this list, deliberately

Things that looked like conflicts and turned out not to need you:

- **Money units** — `amount: 4250` meaning ₹4,250 is fine. We send major units as JSON numbers,
  never strings, because `payments.reduce((a, c) => a + c.amount)` would concatenate a string into
  `"42504250"` and render it as a plausible total. (The money *screens* are items 11 and 12; it is
  the unit convention that needs nothing.)
- **Map coordinates** — 0–100 percentages of the bundled image are stored as-is in new `map_x`/`map_y`
  columns. Real latitude/longitude stays separate.
- **Department staff shape** — `staff[]` stays embedded in the department response even though it is a
  join server-side.
- **`staff[].role` mixing `"Supervisor"` with `"Technician"`** — we split rank from job title in the
  database and re-join them into the exact string you render today.
- **Flats that were never created** — the backend creates a unit on first reference, so `"B-1204"`
  keeps working without an inventory step.

---

## One thing we need from nobody, but you should know

The demo logins (`9876543210` resident, `9999988888` admin, OTP unchecked) do not survive a real
backend. Whoever presents next needs a seeded account. Raising it early so a demo is not lost to it.
