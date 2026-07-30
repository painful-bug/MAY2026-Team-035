# Decisions needed — backend assumptions awaiting an answer

**Raised:** 2026-07-29 · **From:** backend (admin dashboard workstream)
**Covers:** build steps 1–9 (migrations `0010`–`0017`, 70 endpoints)
**Last updated:** 2026-07-30 — step 9 added A22–A24, B17, C7–C8, D8, E21–E24, and **answered A10**

---

## How to use this document

Every item below is something the backend **had to decide in order to keep building**. Each one was
decided, shipped, and isolated so it is cheap to reverse. **None of them is blocked** — this is a
review list, not a stop-the-line list.

Each item has the same shape:

> **What we assumed** — what the code does today
> **Why** — the reasoning, so you can disagree with the reasoning and not just the conclusion
> **Cost if wrong** — how expensive it is to change
> **Answer** — a blank line to write on

**Please answer inline** — edit this file, fill in the `Answer:` lines, commit. Anything you leave
blank we will keep doing as described.

**Priority key:** 🔴 answer before the next build step · 🟡 answer this week · 🟢 whenever

---

## Section A — Product owner

### A1 🔴 Two SLA systems exist and never meet. Which one is real?

The frontend contains **two independent SLA mechanisms** that have never collided only because
complaints do not reference departments in the demo:

| Source | Rule | Where |
|---|---|---|
| Department SLA | 4h (Security) to 48h (Facilities), fixed per department | `data/departments.js` → `slaHours` |
| Urgency table | High 24h, Medium 48h, Low 72h, ignores department | `createComplaintsSlice.js:5` |

A "High urgency" plumbing complaint is due in **24 hours** by one rule and **24 hours** by the other —
coincidence. A "Low urgency" security complaint is due in **72 hours** by one and **4 hours** by the
other. They disagree by 18×.

> **What we assumed** — precedence order: (1) an explicit `sla_hours` override on the category,
> (2) the claiming department's `sla_hours`, (3) the urgency table as fallback. Encoded in one
> function, `complaint_due_at()`.
> **Why** — a department's SLA is a commitment someone made; an urgency table is a default for
> complaints nobody has assigned an owner to. So the specific beats the generic.
> **Cost if wrong** — one function body. Every due date recomputes on next write; existing rows keep
> their stored `due_at` unless we backfill.
>
> **Answer:** ______________________________________________

### A2 🔴 Should urgency change the deadline at all?

> **What we assumed** — **no multiplier.** Urgency selects the *fallback* SLA and nothing more.
> **Why** — I previously invented "high = ½ the SLA, medium = 1×, low = 2×" because R9 said `due_at`
> derives from "the category SLA and urgency" without saying how. **That was retracted** on finding the
> frontend already had a concrete rule. Applying a multiplier *on top of* the urgency-based fallback
> would count urgency twice.
> **Cost if wrong** — one function body, same as A1.
>
> **Answer:** ______________________________________________

### A3 🔴 Can one complaint category belong to two departments?

`Departments.jsx:211` is a multi-select and nothing stops two departments both claiming "Plumbing".
If two claim it, *"which department's SLA applies?"* has no answer in the data — and the SLA decides
whether a complaint is breaching.

> **What we assumed** — yes, it is allowed (join table built), and the **lowest `sla_hours` wins**.
> **Why** — we cannot change the frontend, so the schema must store what the UI emits. The tie-break
> is a workaround, not an answer.
> **Cost if wrong** — if the answer is "no, one owner", the join table becomes a one-to-many and the
> frontend needs a change (disable already-claimed categories). Also on the frontend agenda as item 2.
>
> **Answer:** ______________________________________________

### A4 🔴 Approving a registration issues an invite — it does not create an account. Correct?

The demo's `acceptRequest` creates a fully `Active` resident the instant an admin clicks Approve.

> **What we assumed** — approval marks the request approved and **mints an invitation** the applicant
> must redeem. They are not active until they do.
> **Why** — the standing ruling is that the invite token is a mandatory second factor. Creating a live
> account on approval would bypass it. The admin still sees the request leave the pending list, which
> is what the screen actually reacts to.
> **Cost if wrong** — moderate. Reverting means provisioning an auth user at approval time, which
> re-opens the question of how they authenticate afterwards.
>
> **Answer:** ______________________________________________

### A5 🟡 "Remove resident" deactivates rather than deletes. Correct?

> **What we assumed** — the membership is marked `inactive` and the open residency ends. **There is no
> hard-delete endpoint.**
> **Why** — complaints, invoices and payments reference the membership. Deleting the row would either
> cascade that history away or fail outright. The member disappears from active lists and the flat
> reads as vacant, which is what the screen shows.
> **Cost if wrong** — if a genuine "erase this person" is required (e.g. a data-protection request), it
> is a new, separate operation, not a change to this one.
>
> **Answer:** ______________________________________________

### A6 🟡 An admin cannot remove their own membership. Correct?

> **What we assumed** — refused with `409`.
> **Why** — there is no recovery path in the product from locking a community out of its own
> dashboard. No "last admin" check exists either, so a self-removal could strand a community.
> **Cost if wrong** — one line.
>
> **Answer:** ______________________________________________

### A7 🟡 One invite per phone, or one per flat?

The frontend creates **one user record per phone** for a flat, then mints **one invite token** covering
all of them; redeeming activates every user of that `apartmentId`.

> **What we assumed** — nothing yet; the existing invitation endpoint is unchanged. **We recommend one
> invite per phone.**
> **Why** — one person redeeming should not activate their neighbours' accounts, and today it does.
> **Cost if wrong** — low now, high later. This decides what "Add Resident" returns. Also frontend
> agenda item 5.
>
> **Answer:** ______________________________________________

### A8 🟡 Is `designation` an open list?

President / Secretary / Treasurer / Committee Member / Association Manager / Other.

> **What we assumed** — free text, **no database constraint**.
> **Why** — the list is a frontend display vocabulary that will grow, and a `CHECK` constraint turns
> every addition into a migration.
> **Cost if wrong** — adding a constraint later requires cleaning whatever has been typed by then.
>
> **Answer:** ______________________________________________

### A9 🟢 Is self-service registration submission out of scope for us?

> **What we assumed** — yes. We built the **admin-facing review half only** (list / approve / reject).
> There is no public endpoint to *submit* a request.
> **Why** — you scoped this workstream to the admin dashboard and said registration is handled
> elsewhere. The `registration_requests` table exists and is ready for a submit endpoint.
> **Cost if wrong** — small: one endpoint plus a rate limit (see F3).
>
> **Answer:** ______________________________________________

### A10 🟢 Community timezone — is IST safe to hard-code? — **ANSWERED by step 9**

> **What we originally assumed** — **IST (UTC+05:30)**, fixed offset, for all server-rendered dates,
> because no timezone was stored anywhere in the live schema or the ERD.
> **What changed in step 9** — `community_settings.timezone` now exists, defaults to `Asia/Kolkata`,
> and is settable at `PUT /settings`. It is a real IANA name validated against the database's own
> `pg_timezone_names` catalogue, so a DST-observing community is expressible.
> **What is still true** — `app/core/formatting.py` still renders with the fixed IST offset. **The
> column is stored and not yet read by anything.** Wiring it up is one function, and the reason it was
> not done in the same step is that it changes the strings on every screen at once, which deserves its
> own change rather than riding along with a settings form.
> **This vindicates the amenity design rather than reversing it** (D7 point 2, E19). A booking made for
> 07:00 must still read 07:00 after somebody *corrects* a wrong timezone, which is only true because
> `0016` stores wall-clock `date` + `time`. What the timezone unlocks is anything needing an absolute
> instant — a reminder, a scheduled billing run, "is this booking finished".
> **What we still need** — confirmation that `Asia/Kolkata` is the right default, and whether an admin
> should be free to change it at all. Changing it after bookings exist does not move any booking, but
> it does move the moment a deposit becomes refundable.
>
> **Answer:** ______________________________________________

### A11 🟡 Deleting a department really deletes. Deactivating is never blocked. Correct?

> **What we assumed** — `DELETE /departments/{id}` is a **real delete** (category claims and the
> staff directory go with it; complaint records survive with their `departmentId` cleared), refused
> with `409` while the department owns any open complaint. **Deactivating is never refused.**
> **Why** — the dashboard's own confirmation dialog says *"This permanently removes its
> configuration and staff directory. Complaint records will remain available"*, and it offers
> **Deactivate** as the escape hatch precisely when deletion is refused (`Departments.jsx:569`).
> Guarding both would leave an admin holding a department they can neither delete nor deactivate.
> **This corrects our own build plan**, which had the guard on archiving instead of deletion.
> **Cost if wrong** — low. Making the delete a deactivation is one RPC body; adding the guard to
> deactivation is three lines. Neither touches the API shape.
>
> **Answer:** ______________________________________________

### A12 🟡 Removing a staff member deactivates the row. Correct?

> **What we assumed** — `DELETE …/staff/{id}` marks the row `inactive`; it never deletes. Same
> for members dropped from a `PUT …/staff` roster.
> **Why** — a complaint's `assignee` records staff **by name** (the field is free text — B2),
> so deleting the roster row turns every past assignment into an unattributable string. Removing the
> head also frees the head slot in the same statement, so promotion is never blocked by a former one.
> **Cost if wrong** — low, but note the asymmetry: switching to a hard delete loses history that
> cannot be recovered, while switching away from one loses nothing.
>
> **Answer:** ______________________________________________

### A13 🔴 There is **no maintenance amount anywhere in this product**. What is it?

> **What we found** — the amount a flat is billed does not exist as configuration. It exists as the
> literal `4250` inside `createPendingRequestsSlice.js`'s approval handler, repeated in
> `data/payments.js`. No screen sets it, and the ERD has no rate field either. **This is the first
> thing a real backend needs in order to bill anybody, and it was missing.**
> **What we did** — added `community_billing_settings.default_maintenance_amount`, nullable, with
> `GET`/`PUT /billing-settings` behind it. A billing run with no amount configured and none supplied
> returns **409** rather than falling back: silently adopting a demo constant would bill a real
> community a number nobody chose, and the first anyone would know is a resident's invoice.
> **What we need** — the real number, or confirmation that it varies per flat (by area, by
> occupancy) — which would be a different schema, not a different value.
> **Cost if wrong** — low while it is one number; **high if it is per-flat**, because that is a
> column on `apartments` and a different billing run.
>
> **Answer:** ______________________________________________

### A14 🟡 Billing runs skip vacant flats. Should an empty flat still owe maintenance?

> **What we assumed** — `POST /maintenance-runs` bills every flat with a current resident.
> A flat with no open residency is skipped.
> **Why** — a real association bills the **owner**, and an empty flat usually does still owe. But
> nothing in this product records ownership: `unit_residencies.relationship` can say `owner`, and a
> vacant flat has no residency row at all, so an absent owner is invisible to us. Occupancy is the
> only signal that exists.
> **Cost if wrong** — moderate. Billing vacant flats needs an owner record, which is a new table or
> a new column plus a way to populate it — not a rule change.
>
> **Answer:** ______________________________________________

### A15 🟢 A partially paid invoice reads `Unpaid` on the collections screen. Correct?

> **What we assumed** — the screen's two-value filter maps `draft`, `issued` and `partially_paid`
> all to `Unpaid`; only a fully settled invoice reads `Paid`. `statusDetail` carries the real value.
> **Why** — the question the screen asks is "does this flat owe us anything", and a half-paid
> invoice does. Reading it as `Paid` would hide a receivable.
> **Note the consequence** — the row's `amount` stays the **full** invoice value, because the column
> is headed "Amount". So a client that sums `amount` over `Unpaid` rows overstates receivables once
> partial payments exist. `GET /invoices/summary` sums the balances instead and is correct. Raised
> with the frontend team as agenda item 11.
> **Cost if wrong** — one mapping table entry.
>
> **Answer:** ______________________________________________

### A16 🟢 Overpayment is refused. Correct?

> **What we assumed** — recording a payment larger than the outstanding balance returns **409**.
> The invoice is not settled and no money is recorded.
> **Why** — the alternative is to clamp it, which accepts the money and then loses the difference
> with no record that it ever arrived. A refusal at least tells the admin the two numbers disagree
> while they still have the payer in front of them.
> **If a real overpayment happens** it needs a credit note, which is a concept this schema does not
> have yet.
> **Cost if wrong** — low: allowing it is two lines and a nullable `credit_amount`.
>
> **Answer:** ______________________________________________

---

### A17 🔴 The frontend has **two unrelated amenity products**. Which one is real?

> **What we found** — `src/features/amenities/` is a 114-file subsystem: a catalogue, a per-amenity
> workspace with four tabs, a resident booking flow with multi-day series, and a financial ledger
> with deposits, refunds and damage deductions. `src/data/amenities.js` plus
> `store/slices/createAmenitiesSlice.js` is a **second, unrelated one**: four amenities with ids
> `a1`–`a4`, a `timing` display string, a status of `Available` | `Bookable` | `Open` |
> `Under Maintenance`, and bookings whose time is the string `'07:00 AM - 08:30 AM'`. Nothing links
> them — not the ids, not the field names, not the status vocabulary. The resident Amenities screen
> reads the first; ResidentLandingPage reads the second.
> **What we did** — built the first, because it is the one the admin dashboard uses and the one the
> ERD describes.
> **What we need** — confirmation, and a decision about the landing page. An amenity cannot have both
> `timing: '06:00 AM - 10:00 PM'` with `status: 'Bookable'` **and** a five-group settings object; no
> backend can serve both shapes at once.
> **Cost if wrong** — high. If the second model is the real one, the whole of `0016` is the wrong
> schema, not a wrong field.
>
> **Answer:** ______________________________________________

### A18 🔴 The cleaning buffer currently makes shared capacity unreachable. Confirm we fixed it?

> **What we found** — `validateBookingSlot` rejects any booking overlapping a cleaning buffer, in
> **every** booking mode. Follow that through on the seeded gym — mode `Shared`, capacity 24, buffer
> 15 minutes: an existing 07:00–09:00 booking produces a buffer at 09:00–09:15, so a second resident
> asking for 07:30–09:30 is refused, and so is every other overlapping request. **A shared amenity
> with a non-zero buffer accepts exactly one booking at a time**, and its capacity of 24 can never be
> reached. The seed data hides it: no two gym bookings overlap.
> **What we did** — the buffer blocks only bookings that occupy the amenity **exclusively**
> (exclusive-mode amenities, and private bookings on hybrid ones). Between two shared bookings,
> capacity governs — a shared amenity is not vacated between them and there is nothing to clean
> between two people using the gym at once.
> **This is a deliberate behavioural difference from the demo**, which is why it is 🔴 rather than a
> footnote: bookings the demo refuses, we accept.
> **Cost if wrong** — moderate. Reverting is one clause in one trigger, but any bookings taken in the
> meantime would then be over capacity by the old rule.
>
> **Answer:** ______________________________________________

### A19 🟡 One click now approves a whole multi-day request. Correct?

> **What we found** — `createResidentAmenityBookingSeries` creates one booking record per date and
> `approveAmenityBookingRequest` approves exactly one of them. So a resident asking for the hall on
> three consecutive days appears in the approvals table three times, and an admin can approve Monday,
> reject Tuesday and forget Wednesday.
> **What we assumed** — one request, one decision. `GET /amenities/{id}/approvals` returns one row
> per request with `dayCount` and `dates`.
> **Why** — a resident planning a three-day event does not want two of the three days, and an admin
> clicking "approve" believes they have answered the request.
> **Cost if wrong** — low. Per-day approval is the same data with the decision moved down a level.
>
> **Answer:** ______________________________________________

### A20 🟡 Deleting an amenity with bookings is refused. Correct?

> **What we assumed** — `DELETE /amenities/{id}` succeeds only for an amenity nobody has ever booked;
> otherwise it returns **409** naming the count and pointing at deactivation.
> **Why** — the cascade would take the bookings, their charges and their financial events with it,
> **including deposits residents are still owed**. The catalogue's delete button reads as tidying up
> a list; it would be destroying a financial record.
> **Cost if wrong** — low. Admins who genuinely want it gone deactivate it, and it disappears from
> every booking screen either way.
>
> **Answer:** ______________________________________________

### A21 🟢 A booking deposit is a second money system, parallel to invoices. Correct?

> **What we found** — the ledger tracks deposits held, damage deducted and refunds paid out. An
> invoice models none of that: it cannot be partially refunded to a resident's hand, and a security
> deposit is not revenue.
> **What we did** — followed the ERD, which gives amenity charges their own tables and links them to
> invoicing through one nullable column (`invoice_line_items.amenity_booking_charge_id`, added in
> `0016` as `0015` promised).
> **What we need** — confirmation that deposits are money the association *holds* rather than money it
> *earns*. The distinction matters to whoever reconciles the bank account.
> **Cost if wrong** — moderate; it is an accounting question, not a schema one.
>
> **Answer:** ______________________________________________

### A22 🔴 The Settings screen offers automatic billing and late fines. Neither exists. What are they?

The screen (`pages/AdminDashboard/Settings.jsx`) shows two switches whose labels promise machinery
this product does not contain:

| Switch | What the label promises | What exists |
|---|---|---|
| Automated Monthly Maintenance | invoices raised on a schedule | `POST /maintenance-runs`, pressed by hand |
| Late Payment Fine Charges | a fine added to overdue dues | nothing at all |

> **What we did** — stored both as policy: `auto_billing_enabled` / `auto_billing_day`, and
> `late_fee_enabled` / `late_fee_amount` / `late_fee_grace_days` / `late_fee_period`. **Nothing reads
> any of them.** There is no scheduler in this repository and no fine engine.
> `POST /maintenance-runs` deliberately ignores `autoBillingEnabled` — an admin pressing the button has
> said what they want more recently than a toggle did.
> **What we did not do** — invent either. A scheduler needs a decision about *what runs it* (Supabase
> `pg_cron`, an external worker, a human with a calendar reminder); a fine engine needs to know whether
> a fine is an invoice line, a separate invoice, or a balance adjustment, and whether it compounds.
> **`late_fee_amount` is null until somebody sets it**, and the screen's prose ₹100 was deliberately
> not adopted as a default — that is exactly the A13 mistake, a number nobody chose that is
> indistinguishable from one they did.
> **What we need** — for each of the two: is it real, and if so what runs it and what does it produce?
> **Cost if wrong** — the *storage* is free either way. Building either feature is a step of its own,
> and the fine engine is the larger one because it touches money that residents will dispute.
>
> **Answer:** ______________________________________________

### A23 🟡 Two settings toggles are stored and read by nothing, because their features have no backend

> **What we found** — the other two switches on the same card describe features that exist only as
> frontend dummy data: **Gate Security App Pre-approvals** (there is no visitor table, endpoint or
> migration anywhere) and **Urgent Notice SMS Broadcast** (there is no SMS provider in this
> repository).
> **What we did** — stored them as `require_visitor_preapproval` (default `true`) and
> `notice_sms_broadcast_enabled` (default **`false`**), and said so in `API.md` §11 rather than leaving
> it to be discovered. The SMS default is the deliberate one: it is the only toggle in the product that
> would spend money every time it fired, and a setting like that defaults off.
> **Why store them at all** — because the screen currently *loses* them, which is worse. A policy that
> survives a reload is one a visitor feature can be built against.
> **What we need** — confirmation that `true` / `false` are the right defaults, and — for the SMS one —
> who owns the provider account and its bill.
> **Cost if wrong** — one default value each.
>
> **Answer:** ______________________________________________

### A24 🔴 Should turning a feature module off actually switch the feature off?

Ten modules are chosen during onboarding. `PATCH /settings/modules/{key}` now toggles them. **Nothing
in the product changes when you do.**

> **What we did** — reported module state; **did not enforce it**. No endpoint checks whether its
> module is enabled, and no service imports the settings service.
> **Why we declined to guess** — two reasons, both visible only from the seed data:
>
> 1. **`amenities-booking` ships disabled.** Its `defaultEnabled` in `onboardingModules.js` is `false`,
>    and `0011` seeded it that way. Enforcing the rule would `403` **all twenty-two step-8 endpoints on
>    every community that exists**, which is a data-driven outage rather than a feature.
> 2. **Six of the ten modules have no backend to gate.** The rule would be real for four keys and
>    decorative for six, which is the kind of half-rule people build assumptions on.
>
> **What we did instead** — `module_catalogue.backend_status` (`implemented` / `partial` / `none`) plus
> a `backendNote` per module, and an `enabledWithoutBackend` count on the response. The state is
> reported honestly rather than enforced wrongly, so an admin switching on Parking Management can be
> told nothing will happen.
> **What we need** — a decision in three parts: (a) should a disabled module `403` its endpoints or only
> hide its navigation? (b) if it `403`s, what fixes `amenities-booking` being seeded off — a data
> migration, or is off genuinely the intended default? (c) does a disabled module hide *existing* data
> or just prevent new writes?
> **Cost if wrong** — low to add (one dependency, mirroring `require_role`), and the honest answer is
> that adding it later is safer than adding it now, because every endpoint it would guard is already
> written and tested.
>
> **Answer:** ______________________________________________

## Section B — Frontend team

Full detail is in [`FRONTEND_MEETING_AGENDA.md`](FRONTEND_MEETING_AGENDA.md); this is the short form.
**Nothing here blocks us** — every item is already absorbed by the API.

| # | Item | What we need | Status if you say nothing |
|---|---|---|---|
| B1 🔴 | **Bug: `C-C-505`.** `createPendingRequestsSlice.js:36` builds `` `${tower}-${flat}` ``, but seeded requests already store the full code. Approving a seeded request creates a flat that does not exist. | Pick one meaning for `flat` and use it in both places | We normalise both shapes; your local state stays wrong |
| B2 🔴 | **Free-text assignee** (`Complaints.jsx:175`) | Make it a select over department staff | We store a text label; "complaints assigned to me" stays impossible |
| B3 🟡 | **Category multi-select** lets two departments own one category | Confirm whether that is intended (see A3) | Lowest SLA wins |
| B4 🟡 | **`timeAgo` / `date` are pre-formatted**, so those responses can never be cached | Format relative times client-side | Works, permanently slower and uncacheable |
| B5 🟡 | **No empty states** — a real founding community has zero of everything | An empty rendering per list and tile | Every list returns `{items: [], total: 0}` with `200`; the screens still need to draw it |
| B6 🟢 | **Labels used as foreign keys** (`flat: "B-1204"`, `head: "Ramesh Kumar"`) | Nothing urgent | We send `unitId` beside `flat`; adopt whenever convenient |
| B7 🔴 | **Onboarding promises module editing** that does not exist on Settings. `FeatureConfigurationPage.jsx:79` says *"These features can be changed later from the Admin Settings page."* No such UI exists, and nothing in the frontend reads `enabledModules` — `AdminLayout.jsx:34-43` is a fixed ten-item nav array. **Raised from 🟢 by step 9: the endpoints now exist, so this is the only missing half.** | A module toggle list, calling `GET /settings/modules` and `PATCH /settings/modules/{key}` | Three module endpoints nobody calls, and a promise the product breaks |
| B8 🟢 | **Demo logins do not survive a real backend** | Someone needs a seeded account before the next demo | — |
| B9 🟡 | **The two department-create screens disagree about categories.** `Departments.jsx:22` is a fixed checkbox list of six; `CreateDepartment.jsx:79` is a free-text box whose placeholder is *"e.g. Leaking pipes"* — a symptom, not a category. Only five are seeded; `Others` is not one of them. | Decide whether categories are a controlled vocabulary or free text, and make both screens agree | We upsert by name, so both screens work — and a typo silently becomes a new category |
| B10 🟢 | **`head` is free text independent of `staff[]`.** Nothing makes the head one of the listed staff, though the seed data always does. | Make it a select over the roster | Naming a head promotes the matching staff row, or creates one if no name matches |
| B11 🟡 | **The money tiles are computed in the browser from the whole invoice array** (`Maintenance.jsx:11-17`, `AdminHome.jsx:25-29`). That is correct only while every invoice fits in one response — after that the tiles silently report the total of one page. | Read the tiles from `GET /invoices/summary` instead of summing rows | The table pages correctly and the tiles above it quietly go wrong; the endpoint exists and is ignored |
| B12 🔴 | **There is no way to bill anyone from the dashboard.** The Maintenance screen lists invoices and shows three tiles; no screen creates an invoice, records an offline payment, or sets the maintenance amount. | An invoice-creation screen, a “run billing” action and a billing-settings form | The endpoints exist and a real community's collections screen reports on an empty table forever |
| B13 🟢 | **`Payments.jsx:113` renders `Method: **{inv.paymentMethod}**`** — JSX, not markdown, so residents see literal asterisks around the method. | Remove the asterisks or use `<strong>` | Cosmetic; we send the method exactly as the seed data spells it |
| B14 🟡 | **The amenity reports page computes all six KPIs in the browser** (`amenityReportsService.calculateAmenityReports`), including one labelled **Total Revenue**. Same failure as B11, on a money figure. | Read `kpis` from `GET /amenity-reports` and use `rows` only for the table | The table pages correctly; the revenue figure quietly becomes the revenue of one page |
| B15 🟡 | **The approvals table cannot say how many days a request covers.** One click now decides the whole request, and a three-day booking rendered as its first day alone would tell an admin they are approving one day. | Render `dayCount` (and `dates`) on the approval row | Admins approve more than the row shows |
| B17 🔴 | **The admin Settings screen saves nothing.** `Settings.jsx` is four `useState` toggles and `handleSave = () => showToast('Admin Settings Saved Successfully')`. No store slice, no service module, nothing persisted — an admin flips four switches, is told they saved, and loses all four on reload. It is the only screen in the product whose save button is a lie, which is why **every field name in `API.md` §11 is ours**: there was no existing shape to match. | Wire the four toggles to `GET`/`PUT /settings` and `PUT /billing-settings`, and rename any field where you prefer a different word — now, while nothing depends on them | The endpoints persist correctly and the screen keeps discarding what an admin typed |
| B16 🟢 | **The amenity card's two badges are stored constants in the mock** — the gym claims 5 pending requests against 1, and ₹4,800 in dues against ₹1,600 in charges. | Nothing: use the values as sent | We derive both; your numbers start being right |

> **Answer / meeting notes:** ______________________________________________

---

## Section C — Auth & security workstream owner

You own the privilege-escalation fix in `handle_new_user()` and the tenant-scoping of `is_admin()`.
These are the points where our two streams touch. **We have not modified any auth code.**

### C1 🔴 Please add `email` to `handle_new_user()`

> **What we did** — added `profiles.email` and backfilled it from `auth.users` in migration `0012`.
> **What we did not do** — keep it current for *new* users. That belongs in `handle_new_user()`, which
> is yours.
> **Why it matters** — the Residents screen renders an email address. Without this, every user created
> after the backfill has a null one.
>
> **Answer:** ______________________________________________

### C2 🔴 Migration numbers `0004`–`0009` are reserved for you

> **What we assumed** — you take `0004`–`0009`; dashboard migrations start at `0010`.
> **Why** — both streams would otherwise reach for `0004`, and a filename collision in schema
> *ordering* is the worst place to have a merge conflict.
> **Please confirm** you have not already used `0010`+.
>
> **Answer:** ______________________________________________

### C3 🟡 `current_association_id()` is yours; ours is `current_community_ids()`

> **What we assumed** — you will define `current_association_id()` as part of the §1.2 fix. We
> deliberately did **not** define it, and used a differently-named, set-returning helper instead
> (a person can belong to more than one community).
> **Consequence** — our tables are already community-scoped, so **they do not inherit the unscoped-admin
> hole** while your fix is in flight. When yours lands, adopting it is one line per policy, or nothing.
>
> **Answer:** ______________________________________________

### C4 🟡 Your `handle_new_user()` fix does not break invite redeem — please sanity-check

> **What we checked** — `invitation_service.py:187` calls `upsert_profile_role(...)` explicitly right
> after `auth.admin.create_user`. So when you stop trusting `raw_user_meta_data` for the role, the
> redeem path still ends with the correct role. It passes `role` in metadata today, but does not
> *depend* on the trigger reading it.
> **Please confirm** you read it the same way.
>
> **Answer:** ______________________________________________

### C5 🟡 When OAuth lands, what identifies an invitee?

> **Context** — `invitations.phone` is the join key today, and redeem calls
> `sign_in_with_password` after creating a phone-confirmed user. Under OAuth the user arrives with an
> email identity and possibly no phone at all.
> **What we assumed** — nothing. We have not touched the redeem path.
> **Why it matters** — this decides whether `invitations` needs an `email` column, and whether an invite
> is bound to a person or merely to a flat.
>
> **Answer:** ______________________________________________

### C6 🟢 `backend/.venv` is committed — 4,100+ files

> **What we did** — nothing. `git rm -r --cached` rewrites the index across thousands of paths and
> wants its own commit on a clean tree, not a fold-in to a migration PR.
> **Who should do it and when?**
>
> **Answer:** ______________________________________________

### C7 🔴 §1.2 is now the only thing standing between an admin and renaming their community

> **What we found** — `associations` is the **one table this build plan touches** whose admin write
> policy is the unscoped `associations_admin_write ... using (public.is_admin())` from `0002_rls.sql`.
> Any admin of any community satisfies it.
> **What we did** — **wrote no endpoint that writes `associations`.** `GET /settings` reports the
> community's `name`, `communityType` and `status`; nothing sets them. A rename would be the first of
> seventy operations to depend on that policy, and we would rather not be the reason it becomes urgent.
> **What this costs** — an admin cannot correct a typo in their own community's name. That is a real
> gap in the settings screen and it is deliberate.
> **What we need** — a nudge when the §1.2 fix lands. Adding `PUT /settings/community` afterwards is
> one RPC and one endpoint, and we will do it then rather than now.
>
> **Answer:** ______________________________________________

### C8 🟡 `inviteTtlHours` is now a stored community setting. The invite path still reads the env var

> **What we did** — added `community_settings.invite_ttl_hours` (default 72, capped at 720) and exposed
> it at `GET`/`PUT /settings`. An admin can set it today.
> **What we did not do** — make anything read it. `invitation_service.py` still takes the TTL from an
> environment variable, and **that file is yours** — the standing rule is that we do not touch
> auth-adjacent code while you are working in it.
> **Why the cap is 720 hours** — thirty days. An invite that outlives a month is not a second factor any
> more, it is a credential sitting in an inbox. If you disagree, the cap is one `CHECK` and one
> validator.
> **What we need** — either you adopt the column when convenient (one query, community-scoped), or you
> tell us the env var is deliberately global and we will mark the column as advisory in `API.md`. Two
> sources of truth for how long an invite lives is the outcome to avoid.
>
> **Answer:** ______________________________________________

---

## Section D — ERD / class diagram owners

**We have not edited the ERD, the DBML, the class diagram or the component design.** All of these are
requests, not changes already made.

### D1 🔴 `units` means the opposite thing in the ERD and the live database

| Concept | Live DB | ERD |
|---|---|---|
| The community | `associations` | `communities` |
| A block or villa | **`units`** | `buildings` |
| A flat / home | `apartments` | **`units`** |

> **What we assumed** — **additive now, rename by agreement later.** New tables use ERD *column* names
> (`community_id`, `unit_id`) while pointing at today's tables, so the rename stays one mechanical
> migration and no auth code changes.
> **Why it matters** — a developer reading the ERD and writing a query against the database gets flats
> when they wanted blocks, silently, with no type error.
> **Please confirm** the rename is the intended destination, and who owns it.
>
> **Answer:** ______________________________________________

### D2 🟡 `complaint_events` was in the ERD but in no migration

> **What we did** — created it in `0013`. It is **append-only, structurally**: there is no `UPDATE` or
> `DELETE` policy on it, so it cannot be edited even by an admin.
> **Why** — R9 resolved "management notes" with *"no column — `complaint_events` already has `note`"*,
> but that table existed only on paper. The admin's "Resident-visible Update" box writes to it.
> **Please check** our shape against the ERD's: `{event_type, label, message, actor_membership_id,
> actor_label, created_at}`.
>
> **Answer:** ______________________________________________

### D3 🟡 R1 was **not** applied, contradicting our own earlier plan

> **What we assumed** — R1's two partial unique indexes do **not** belong on `apartments`.
> **Why** — R1 addresses a *block-relative* label (`101` recurring per building) where a nullable
> `building_id` makes NULLs distinct. But `apartments.code` is `B-1204` — the frontend builds it as
> `` `${tower}-${flatNumber}` ``, so the block is already in the string and per-community uniqueness is
> correct. Applying R1 would have **loosened a constraint that works**.
> **Please confirm** R1 is parked until the ERD's separate `unit_label` column actually exists.
>
> **Answer:** ______________________________________________

### D6 🟡 Three deliberate deviations from the ERD in the money tables

> **1. `invoice_number` is unique PER COMMUNITY, not globally.** The ERD marks it globally
> unique. The number is built from a per-community prefix that defaults to `INV` for everyone,
> so under a global constraint the second community to exist could never issue its first
> invoice.
>
> **2. There is no `overdue` status.** The ERD's `InvoiceStatus` lists one. A stored overdue
> flag is correct only in the instant a cron job sets it and wrong every hour after that, so
> `invoice_overview.is_overdue` derives it from the due date and the balance. It is left out of
> the CHECK entirely rather than allowed-but-never-written, because a value that is legal to
> store invites someone to store it.
>
> **3. `payments.payer_profile_id` is nullable** (the ERD says not null). An admin recording
> cash for a flat whose resident has already moved out has no payer to name, and requiring one
> would make them invent a person. The unit is the debtor; the payer is enrichment.
>
> **Cost if wrong** — low for all three **while `0015` is unapplied**. After it is applied,
> (1) and (3) become data migrations.
>
> **Answer:** ______________________________________________

### D7 🟡 Five deliberate deviations from the ERD in the amenity tables

> **1. `amenity_settings` replaces `amenity_rules`.** The ERD's rules table is versioned
> (`effective_from` / `effective_to`) and weekday-scoped, and **no screen writes either axis**. It
> also covers 8 of the ~30 fields the settings tab saves — nothing for the cleaning buffer, slot
> duration, waitlist, auto-approval, same-day bookings, guest bookings, recurring bookings, refund
> policy, damage deposit, closed days, maintenance days, holiday overrides, temporary closure,
> minimum duration, or the entire maintenance group. One row per amenity holds all of them.
> `amenity_settings` is a **superset** of `amenity_rules`, so adding the versioning axis later is one
> migration rather than a rewrite.
>
> **2. Occurrences store `booking_date date` + `starts_at time` + `ends_at time`, not two
> `timestamptz`.** A `timestamptz` makes "07:00" mean whatever the server's zone says, and there is
> **no community timezone field anywhere in the product** to resolve it against (see A10). Opening
> hours are wall-clock. The generated `tsrange` columns give the exclusion constraint what it needs
> without inventing a zone.
>
> **3. The ERD's note on overlap is only correct for exclusive amenities.** It reads: *"Active
> occurrences for the same amenity must not overlap; enforce with a PostgreSQL time-range exclusion
> constraint."* The gym has capacity 24 and mode `Shared` — overlapping bookings are the point of it,
> and a blanket exclusion constraint would make `capacity` a number nothing reads. Overlap is guarded
> by a scoped exclusion constraint **plus** a trigger holding an advisory lock, because an `EXCLUDE`
> predicate is per-row and cannot express "conflict if *either* side is exclusive", nor count.
>
> **4. `booking_guests` is named `amenity_booking_guests`**, keeping all seven tables of this
> subsystem under one prefix.
>
> **5. `amenities.location` and `amenities.image_url` added**, and occurrence status carries
> `blocked` and `pending`, which the ERD's occurrence status does not name. A maintenance block is not
> a booking anybody made, but it occupies the amenity exactly like one, and a separate table for it
> would duplicate every conflict rule.
>
> **Cost if wrong** — low for all five **while `0016` is unapplied**. (1) and (2) become data
> migrations afterwards.
>
> **Answer:** ______________________________________________

### D8 🟡 Four deviations from the ERD's `community_settings`, and a count that is wrong

> **1. `enabled_modules jsonb` became a table, `community_modules`.** The ERD stores the enabled module
> keys as a jsonb array on `community_settings`. A jsonb array cannot record **when** a module was
> switched off or **by whom**, and "who turned off resident management, and when" is the first question
> anyone asks after it happens. `community_modules` (from `0011`) carries `updated_at` and
> `updated_by_membership_id` per key. `0017` adds `module_catalogue` beside it — the ten keys, their
> labels, their defaults and their `backend_status` — because the ERD names no home for the module
> *definitions* at all, only for the selection.
>
> **2. The catalogue drives the list, not the community's rows.** A community with no row for a key
> reads as that key's default rather than the key vanishing. A jsonb array cannot express "not yet
> chosen" as distinct from "off", and the settings screen needs to: an eleventh module added later must
> appear everywhere immediately.
>
> **3. `default_currency_code` and `invoice_number_prefix` are not in `community_settings`.** The ERD
> puts them there; `0015` had already put them in `community_billing_settings`, where the rest of money
> lives. Two tables owning currency is how two screens start disagreeing about it.
>
> **4. The six billing-toggle columns are also on `community_billing_settings`, not
> `community_settings`.** `auto_billing_enabled`, `auto_billing_day`, `late_fee_enabled`,
> `late_fee_amount`, `late_fee_grace_days`, `late_fee_period`. They are money, they need
> `default_maintenance_amount` in the same row to be checkable, and the two cross-field `CHECK`s that
> make them honest (a toggle cannot be on without the number it acts on) are only writable as
> constraints if all the columns are in one table.
>
> **So `community_settings` holds only what had no home**: `timezone`, `unit_label_singular`,
> `invite_ttl_hours`, `visitor_code_ttl_minutes`, the two policy toggles from A23, and `version`.
>
> **5. The ERD says onboarding "selects nine feature modules". There are ten.**
> `frontend/src/data/onboardingModules.js` has ten, `0011` seeded ten, and the catalogue has ten. This
> is a documentation error rather than a design decision, and it is the kind that silently becomes a
> requirement — **please correct the ERD.**
>
> **Cost if wrong** — low for (3) and (4) **while `0015` and `0017` are unapplied**; (1) and (2) are
> structural and would be a rewrite, not a migration. (5) is a one-word edit to the ERD.
>
> **Answer:** ______________________________________________

### D5 🟢 Should `departments.status` say `inactive` rather than `archived`?

> **What we assumed** — the column keeps `active` / `archived` from migration `0011`, and the
> API translates to the frontend's `Active` / `Inactive` in `app/domain/vocabularies.py`.
> **Why** — each vocabulary has exactly two values, so the mapping is a true bijection and
> nothing is lost. `archived` nonetheless *reads* as terminal, while the dashboard's toggle is
> plainly reversible, so the word may simply be wrong.
> **Cost if wrong** — near zero **while `0011` is unapplied**: change one `CHECK` constraint
> and delete one mapping table. After it is applied it becomes a data migration.
>
> **Answer:** ______________________________________________

### D4 🟢 Class-diagram requests R29–R31 are still open

> The class diagram currently matches the ERD, not the live database. R17c (residency, not role, grants
> resident capabilities) is now structurally true in the schema, which collapses five subclasses.
>
> **Answer:** ______________________________________________

---

## Section E — Everyone: things that are true today and may surprise you

Not questions — statements of current state, so nobody discovers them at the wrong moment.

| | State |
|---|---|
| **E1** | **No migration has been applied anywhere.** `0010`–`0017` are written and unrun. There is no Postgres, `psql`, Supabase CLI or Docker on the machine they were written on. Everything above the database boundary is tested (**275 tests**); the boundary itself is not. `0016` widened this — its correctness rests on things only Postgres can do (a `gist` exclusion constraint, an advisory lock inside a trigger, generated `tsrange` columns) — and `0017` adds one more: its timezone validation reads `pg_timezone_names`, a catalogue that only exists inside a running server. **This is the single largest unknown in the workstream.** |
| **E2** | **Postgres 15 or newer is required.** `ON DELETE SET NULL (column)` is 15+. On 14 the migrations fail at apply time. |
| **E3** | **Nothing is rate-limited**, including `/auth/otp/request` and `/auth/redeem` — the two unauthenticated secret-guessing surfaces. |
| **E4** | **Optimistic concurrency is designed but not enforced.** Last write wins on `PATCH /residents`. The complaint and department edit screens make this likelier to bite. |
| **E5** | **A Supabase Storage bucket named `complaint-attachments` must exist and must be private.** A public bucket makes every complaint photo world-readable by URL, bypassing RLS entirely. |
| **E6** | **`/auth/*` speaks snake_case; everything else speaks camelCase.** Deliberate seam — the auth DTOs are being edited in parallel, and converting them mid-flight would be a drive-by edit. |
| **E7** | ~~`dashboard.collection` is hard-coded zeros~~ — **real as of step 7.** It reads the same database aggregate that serves `GET /invoices/summary`, so the home page and the collections screen cannot disagree about how much has been collected. |
| **E8** | **Nothing has been committed to git**, and `frontend/` has never been modified. |
| **E9** | **`docs/openapi.yaml` is generated, never hand-edited.** Regenerate with `cd backend && python scripts/export_openapi.py`; `--check` fails when it is stale, and the test suite runs that check. Edit the code, not the YAML. |
| **E10** | **Department search runs against a precomputed `search_text` column** in the `department_overview` view, because the dashboard searches name, description, head, email, category names *and* staff names in one box — which no combination of PostgREST filters across embedded tables can express. |
| **E11** | **`GET /departments` embeds each department's roster.** The dashboard seeds its edit modal from the list row, so splitting them would make one screen issue N+1 requests. Costs one extra query per page, not one per department. |
| **E12** | **Money amounts are JSON numbers, not strings, and that is deliberate.** Pydantic serialises `Decimal` as a string; a string reaching `payments.reduce((a, c) => a + c.amount)` concatenates into `"42504250"` and renders as a plausible rupee total. Every total the API reports is computed by Postgres in `numeric` — **nothing is summed in Python.** |
| **E13** | **A double-clicked billing run bills nobody twice.** The guard is a partial unique index on `(community, unit, billing_period_start)`, not a check the API performs — so it holds under concurrency, and a repeat run reports every flat as `skipped`. |
| **E14** | **Recording a payment is idempotent on `reference`.** A replayed gateway webhook returns the payment already recorded rather than crediting the invoice twice. |
| **E15** | **A resident sees their flat's invoices only from the date they moved in.** Liability follows the unit, so a flat's invoice history outlives its occupants — and showing a new tenant the previous occupant's arrears would disclose one resident's debts to another. The RLS policy is bounded by `issued_on >= residency.start_date`. |
| **E16** | **`0016` is the first migration to need an extension.** `btree_gist` must be installable, for the `uuid` equality operator inside the overlap exclusion constraint. It ships with Supabase, but the migration will fail at apply time on a Postgres where it is unavailable. |
| **E17** | **The cleaning buffer no longer blocks shared bookings.** In the frontend it does, in every mode — which makes a shared amenity's `capacity` unreachable (A18). Here it applies only between uses that occupy the amenity exclusively. **Bookings the demo refuses, we accept.** |
| **E18** | **The approvals screen's "outstanding dues" is the FLAT's balance, not the person's.** `amenityBookingsService.js:61-67` computes it per `userId` from the maintenance invoices; our invoices attach to the unit and carry no person. Same label, different number — and for "should I approve this booking" the flat's balance is arguably the better one, but nobody has said so. |
| **E19** | **A booking is "completed" against UTC, not against local time.** So a booking is treated as finished up to the server's offset early or late. It affects only when the deposit becomes refundable and when a row stops offering force-cancel. **Step 9 made this fixable and did not fix it:** `community_settings.timezone` now exists (A10), but the `completed` expression in `0016`'s view does not read it. Doing so is one `at time zone` clause in one view, and it belongs with whatever change makes `formatting.py` read the column too. |
| **E20** | **Nothing in the API decides whether a slot is free.** The conflict and capacity rules live in a `BEFORE` trigger that takes `pg_advisory_xact_lock` on the amenity first, so two residents booking the last place serialise and the second one loses. A service-layer check would be the classic check-then-act race. |
| **E21** | **A settings screen that has never been saved is indistinguishable from a configured one unless you read `hasSavedSettings`.** Every value comes back populated — `Asia/Kolkata`, 72 hours, `Flat` — because a screen asking what the settings are should not get a `404`. `hasSavedSettings: false` is the only thing separating a default from a choice, and a screen that ignores it tells an admin they picked a timezone they have never seen. Same reason `unitLabelIsDerived` exists for one field. |
| **E22** | **`unitLabelSingular` is derived, not defaulted.** With no override, `Flat` for `apartment` and `Villa` otherwise. It is computed at read time rather than written at create time because a stored default goes stale the day a community changes type. **The rule exists twice** — in SQL in `community_settings_overview` and in Python in `vocabularies.unit_label_for` — and `test_settings_mapping.py` pins them against each other, because two copies of one rule is the arrangement that drifts. |
| **E23** | **A toggle cannot be switched on without the number it acts on, and the database is what refuses.** `auto_billing_enabled` while `default_maintenance_amount` is null, or `late_fee_enabled` without a `late_fee_amount` above zero, is `HB409` → `409`. It is a `BEFORE` trigger with `CHECK` constraints as a backstop, rather than a validator in Python, so direct SQL cannot produce a toggle that claims to be on with nothing behind it. **A patch that silently ignored the key would be worse than one that fails**: the API would return `200` and the toggle would spring back on the next read, which is the exact bug the current frontend has. |
| **E24** | **`community_module_overview` and `community_settings_overview` are readable by any member, but only the settings one leaks by being read.** It carries seven columns from `community_billing_settings`, an admin-only table — so a resident selecting it gets `COALESCE` defaults (`0`, `false`, `null`) rather than an error. **Those defaults read as data and are not.** The endpoint is admin-only, which is what actually protects it; the view is admin-only by consequence, and `0017` says so in a comment beside it. |

---

## Section F — Ownerless

Real work with nobody assigned. Flagging rather than silently adopting.

| | Item | Suggested owner |
|---|---|---|
| **F1** 🔴 | Applying the eight migrations (`0010`–`0017`) to a real Supabase project and running the verification queries in each file's footer. **The admin-dashboard build order is now complete, so this is the whole remaining risk**: `0016`'s overlap guard is the only thing standing between two residents and the same hall and it has never executed, and `0017` has one verification query that legitimately *can* return rows — stale `community_modules` keys with no catalogue entry, since `0011` seeded keys before the catalogue existed and no FK was added on purpose | backend + whoever holds the Supabase project |
| **F2** 🔴 | Creating the private `complaint-attachments` Storage bucket | same |
| **F3** 🟡 | Rate limiting on the unauthenticated endpoints | auth workstream |
| **F4** 🟡 | Optimistic concurrency on the edit endpoints — **steps 6 through 9 all shipped without it**; there are now seven last-write-wins surfaces, `PATCH /amenities` and `PUT /settings` included, where two admins editing thirty settings fields will silently overwrite each other. Money and bookings are exceptions and not by concurrency control: no balance is ever written by the API, and slot conflicts are settled by an advisory lock in the database. **Step 9 supplied the handle without using it**: `community_settings.version` increments on every write and nothing checks it, so adopting `If-Match` on that one endpoint is now the cheapest place to prove the pattern | backend, next change |
| **F5** 🟢 | Untracking `backend/.venv` | auth workstream (C6) |
| **F6** 🟡 | **Deciding what happens to a flat's arrears when a resident moves out.** The debt stays with the unit, which is the correct default — but nobody has said whether the departing resident is still pursued for it, and that is a policy question with a legal shape | product owner + whoever handles collections |

> **Answer / assignments:** ______________________________________________

---

## Appendix — every assumption, in one table

For scanning. `A`/`C`/`D` reference the sections above.

| ID | Assumption | Reversal cost |
|---|---|---|
| A1 | SLA precedence: category override → department → urgency table | One function body |
| A2 | Urgency does **not** multiply the SLA (earlier multiplier retracted) | One function body |
| A3 | A category may have two owning departments; lowest SLA wins | Schema + a frontend change |
| A4 | Approval mints an invitation, not an active account | Moderate |
| A5 | Removal deactivates; no hard delete | New operation, not a change |
| A6 | An admin cannot remove themselves | One line |
| A7 | Invite-per-phone recommended, not yet implemented | Low now |
| A8 | `designation` is unconstrained free text | Data cleanup later |
| A9 | Registration *submission* is out of scope | One endpoint |
| A10 | **Answered by step 9.** `community_settings.timezone` exists, defaults to `Asia/Kolkata`, is validated against `pg_timezone_names` — and is not read by anything yet | One function to adopt it |
| A11 | Department delete is a real delete, guarded by open complaints; deactivation is not guarded | One RPC body |
| A12 | Removing a staff member deactivates the row | One RPC body; a hard delete loses history |
| A13 | The maintenance amount is per-community configuration, nullable, and a billing run with none set is refused | Low; high if the rate is per-flat |
| A14 | Only occupied flats are billed | New ownership record, not a rule change |
| A15 | A partially paid invoice reads `Unpaid`; `amount` stays the full value | One mapping entry |
| A16 | Overpayment is refused rather than clamped | Two lines plus a credit concept |
| A17 | The `features/amenities` model is the real one; `data/amenities.js` is not served | High — a different schema, not a different field |
| A18 | The cleaning buffer blocks only exclusive occupation, so shared capacity is reachable | One clause in one trigger |
| A19 | One approval decides a whole multi-day request | Low |
| A20 | An amenity with bookings cannot be deleted, only deactivated | One RPC body |
| A21 | Deposits are money held, tracked separately from invoices | Accounting, not schema |
| A22 | Automatic billing and late fines are stored as policy and read by nothing; no scheduler, no fine engine | Storage free; either feature is a step of its own |
| A23 | Visitor pre-approval defaults on, SMS broadcast defaults **off** — both stored, both read by nothing | One default value each |
| A24 | Module state is reported, never enforced; `backend_status` replaces the guard | One dependency to add later |
| B17 | The Settings screen persists nothing, so its field names are ours | Free while nothing calls them |
| B9 | Unknown category names are created on department save, not rejected | One guard |
| B10 | Naming a head promotes or creates the matching staff row | One helper function |
| B11 | The money tiles are served by an endpoint the frontend does not call yet | Free |
| B12 | No dashboard screen can issue an invoice; the endpoints exist regardless | Free |
| B14 | The reports page's Total Revenue is computed in the browser; the aggregate exists | Free |
| B15 | The approvals row does not render `dayCount`, so one click decides more than it shows | Free |
| B16 | The amenity card's two badges are derived here, not stored | Free |
| D5 | `departments.status` keeps `active`/`archived`; the API maps to `Active`/`Inactive` | One CHECK while unapplied |
| D6 | Invoice numbers unique per community; no stored `overdue`; nullable payer | Data migration once applied |
| D7 | `amenity_settings` replaces `amenity_rules`; local date+time rather than `timestamptz`; overlap guarded by constraint **and** trigger | Data migration once applied |
| D8 | `enabled_modules jsonb` became `community_modules` + `module_catalogue`; currency, prefix and the billing toggles stay in `community_billing_settings`; the ERD's "nine modules" should read ten | Structural for the table split; a one-word ERD edit for the count |
| C7 | No endpoint writes `associations`, so an admin cannot rename their community | One endpoint once §1.2 lands |
| C8 | `invite_ttl_hours` is stored; `invitation_service.py` still reads the env var | One query, in auth-owned code |
| — | Staff `activeAssignmentCount` is scoped to that department | One join condition |
| — | Assignment matching uses an exact prefix, not `ilike` — a name may contain `%` | One expression |
| — | `openapi.yaml` is generated from the code and checked in | Free |
| — | Invoice liability attaches to the unit; `userId` is the current occupant, for display | Structural — the whole money schema |
| — | No invoice is ever deleted; `void` cancels and keeps the number | One RPC body |
| — | The first invoice is **not** seeded at registration approval — approval creates no residency, so there is nobody living there to bill | One call site |
| — | `maintenance_due_day` is capped at 28 so a due date never falls outside February | One CHECK |
| — | Role vocabulary left undecided; staff rank/title kept out of the enum | Free |
| — | `notices.category` free text; complaint categories a table | One table + seeding |
| — | `job_title` stored, not derived from `rank` | Would lose the label |
| — | `complaints.department_id` stored, not derived | Would rewrite history on re-derive |
| — | Flats created on first reference (no inventory step) | Free |
| — | Read state is per person, not a flag on the complaint | Would lose per-person accuracy |
| — | Timeline is structurally append-only (no UPDATE/DELETE policy) | Add a policy |
| — | Attachment bytes bypass the API; client uploads to Storage directly | Rework upload path |
| — | `isBreaching` = deadline passed **and** still open | One expression |
| — | A resident may read every occurrence in their community, but only their own booking series — the calendar needs busy slots, not names. RLS cannot hide a column, so the privacy boundary is a table boundary | Structural |
| — | A refund's amount is computed in Postgres and is not a request parameter | One RPC body |
| — | `paymentStatus` and `completed` are derived, never stored, like `isOverdue` | One view |
| — | An administrative block is a booking row with no unit, not its own table | Would duplicate every conflict rule |
| — | A pending request holds its slot, matching `isAvailabilityBlockingBooking` | One predicate |
| — | `unit_label_singular` is nullable and null means "derive it"; the rule lives in SQL and Python and the two are tested against each other | One expression in two places |
| — | `timezone` is validated in the RPC against `pg_timezone_names`, not by a `CHECK` — a `CHECK` must be immutable and the catalogue is host-loaded | One clause |
| — | `late_fee_amount` is nullable and null means "not configured"; the screen's prose ₹100 was deliberately not adopted as a default | One default, and it would be the A13 mistake again |
| — | The billing toggles are readable at `GET /settings` and writable only at `PUT /billing-settings` — money keeps one writer | One endpoint |
| — | `GET /settings/modules` is unpaginated and readable by **any** authenticated role, unlike the rest of §11 | One dependency |
| — | `module_catalogue` has a read policy and **no write policy at all** — it is seed data, changed by migration | One policy |
| — | `PUT /settings/modules` writes every catalogue key, so a key dropped from the array turns off rather than keeping its old value | One `where` clause |
| C2 | Migrations `0004`–`0009` reserved for the auth workstream | Renumber |
| D1 | Additive now, rename `associations`/`units`/`apartments` later | One mechanical migration |
| D3 | R1 not applied to `apartments` | Two indexes |
