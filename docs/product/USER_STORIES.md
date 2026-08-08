# User stories

> **Source.** Team 035, `user-stories.txt`. Reproduced verbatim; the `US-*` identifiers and the
> per-story **Backend** line are the only additions. See [`README.md`](README.md).
>
> The **Backend** line is a one-word verdict plus a pointer. The evidence — which endpoint, which
> status code, what is missing — is in the traceability matrix at
> [`../API.md` §16](../API.md#16-user-stories--endpoints). Do not maintain the two independently:
> §16 is the working copy, this line is the index.
>
> **It was maintained independently, and it drifted.** Between 2026-08-04 and 2026-08-08 six of these
> lines reported a story as less complete than it was, because §16 and
> [`api_annotations.py`](../../backend/scripts/api_annotations.py) moved together and this file did
> not. Corrected on 2026-08-08, and now checked by
> `cd backend && python scripts/api_map_scan.py`, which reads the verdict from all three places and
> refuses to agree that they agree.

| Verdict | Meaning |
|---|---|
| **Served** | An endpoint exists that does what the story asks, end to end |
| **Partial** | An endpoint exists that does some of it; the shortfall is named |
| **None** | No endpoint. Either out of the admin-dashboard scope, or not built yet |

---

## 1. Administrative staff

### US-1.1 — Partial cancellation of multi-day bookings

**User story:** As an administrator, I want to cancel individual dates within a multi-day amenity
booking, so that a resident is not forced to cancel the entire reservation when only one day changes.

**Interviewee pain points addressed:**

- Multi-day bookings cannot be partially cancelled.
- Residents must cancel the entire booking even when only one day's reservation needs to be removed.

**Backend:** **Served** — `POST /amenity-bookings/cancel`.

### US-1.2 — Auto-sync cancellations to accounts

**User story:** As an administrator, I want cancellations to update the accounts module
automatically, so that financial reconciliation is accurate with no manual re-entry.

**Interviewee pain point addressed:**

- Booking cancellations are not reflected immediately in financial accounts.

**Backend:** **Served** — the ledger derives from the event stream, so there is nothing to sync.

### US-1.3 — Real-time sync across modules

**User story:** As an administrator, I want booking and cancellation changes to reflect across the
resident application, admin portal, and reports immediately, so that everyone sees the current
status.

**Interviewee pain point addressed:**

- Booking and cancellation records occasionally fail to update correctly.

**Backend:** **Partial** — `GET /events` is audience-scoped and reaches every role; no resident
client subscribes to it, and reports are still computed per request rather than pushed.

### US-1.4 — Streamlined resident information update

**User story:** As an administrator, I want to view and update a resident's details from a single
screen, so that profile maintenance is fast and consistent.

**Interviewee pain points addressed:**

- Updating resident details such as email addresses is not sufficiently streamlined.
- Resident information, booking records, reports, and email communication are maintained across
  multiple places.

**Backend:** **Partial** — the single-screen read exists; no endpoint writes a resident's details.

### US-1.5 — Simplified booking management workflow

**User story:** As an administrator, I want streamlined booking workflows with redundant steps
removed, so that routine booking management is faster and less error-prone.

**Interviewee pain point addressed:**

- Some booking workflows remain more complicated than necessary.

**Backend:** **Served** — every booking action is one call.

### US-1.6 — Automated administrative reports

**User story:** As an administrator, I want booking history, amenity billing, and gym subscription
reports generated automatically and exportable in a few steps, so that I spend far less manual
effort compiling them.

**Interviewee pain point addressed:**

- Booking history reports require considerable administrative effort.

**Backend:** **Partial** — the data is computed server-side; export and subscriptions are not.

---

## 2. Resident

### US-2.1 — Reliable visitor approval notifications

**User story:** As a resident, I want a visible push notification for every visitor-approval
request, so that I never have to open the application to find pending entries.

**Interviewee pain points addressed:**

- Visitor approval notifications sometimes produce only a notification sound without displaying the
  actual notification.
- Residents must manually open the application to identify pending visitor approvals.

**Backend:** **Partial** — the resident's *answer* exists (`POST /visitor-passes/{passId}/approve`
· `/reject`) and push is built; nothing writes the *question*, because that is gate software this
repository does not contain.

### US-2.2 — Fast visitor pre-approval

**User story:** As a resident, I want to create a visitor pre-approval in minimal steps, so that I
can authorize guests quickly before they arrive.

**Interviewee pain point addressed:**

- Residents must manually open the application to identify pending visitor approvals.

**Backend:** **Served** — `POST /visitor-passes`, in one call, with the code returned exactly once.

### US-2.3 — One-tap quick access to frequent tasks

**User story:** As a resident, I want one-tap access, including a home-screen widget, to my
most-used actions, so that common tasks do not require deep navigation.

**Interviewee pain points addressed:**

- Frequently used features require multiple navigation steps.
- No quick-access widget is available for commonly used actions such as visitor approvals or guest
  invitations.
- Having many features makes applications harder to navigate when core workflows are not simple or
  reliable.

**Backend:** **Partial** — `GET /resident/snapshot` is the enabling call, and pending passes are
carried whole so answering one is a tap. The home-screen widget is an OS surface a web application
does not have.

### US-2.4 — Reliable notifications for society notices and application updates

**User story:** As a resident, I want reliable push notifications for new society notices and
important application updates, so that I learn about them without having to open the application.

**Interviewee pain point addressed:**

- Important application updates are sometimes available only after opening the application.

**Backend:** **Partial** — `GET /notices` is the resident's read and the push transport exists;
`POST /notices` does not yet call `notify_member`, so nobody is told.

### US-2.5 — Simple complaint submission with priority

**User story:** As a resident, I want to raise a complaint through a minimal form with a priority
selector, so that reporting an issue is fast and correctly categorized.

**Interviewee pain point addressed:**

- The complaint submission process contains too many options and feels unnecessarily complicated.

**Backend:** **Served** — `POST /complaints`, with `urgency` writing to a real `priority` column
(`0031`).

### US-2.6 — Complaint status tracking with history

**User story:** As a resident, I want to see my complaint's current status with a timestamped update
history, so that I can track resolution without calling management.

**Interviewee pain points addressed:**

- Complaint statuses are not updated consistently.
- Residents cannot see meaningful progress, expected resolution time, or ownership of a complaint.
- Repeated calls and follow-ups are often necessary.

**Backend:** **Served** — `GET /complaints/{complaintId}` returns the timestamped history, and
`GET /complaints` returns `progress`. The dashboard snapshot still drops that column; no story
depends on it now.

### US-2.7 — Complaint lifecycle notifications

**User story:** As a resident, I want push notifications when my complaint is acknowledged, updated,
reassigned, or resolved, so that I stay informed without following up.

**Interviewee pain points addressed:**

- Push notifications for complaint updates are occasionally delayed or not delivered.
- Repeated calls and follow-ups are often necessary.

**Backend:** **Partial** — backend-complete: every transition writes a notification and both
transports carry it. `frontend/public/` has no service worker, so no phone can buzz.

### US-2.8 — Complaint accountability

**User story:** As a resident, I want each complaint to show who is responsible and an expected
resolution time, with overdue flagging, so that I know who is handling it and when to expect action,
without repeated follow-ups.

**Interviewee pain points addressed:**

- Residents cannot see meaningful progress, expected resolution time, or ownership of a complaint.
- Repeated calls and follow-ups are often necessary.

**Backend:** **Served** — `assignee`, `expectedResolutionAt` and `isOverdue` reach the raising
resident through `GET /complaints`. The snapshot still drops them; it is no longer the only path.

### US-2.9 — Verified management contact directory

**User story:** As a resident, I want a current, verified management contact directory with clear
roles, so that I can reach the right person quickly.

**Interviewee pain point addressed:**

- Management contact details are outdated, unclear, or insufficiently maintained.

**Backend:** **Partial** — the directory is complete, maintained, and readable by residents through
`GET /directory/contacts`; "verified" is nobody's job yet.

### US-2.10 — Designated building representative

**User story:** As a resident, I want a designated representative for my building shown clearly, so
that I know exactly whom to contact for building-specific issues.

**Interviewee pain point addressed:**

- Residents cannot easily determine which management representative is responsible for their
  building.

**Backend:** **None** — departments have heads; nothing ties a head to a building.

### US-2.11 — Timely notices with effective dates

**User story:** As a resident, I want to be reminded when new rules are about to take effect, so
that I am informed and reminded of changes in policies that are about to take effect.

**Interviewee pain point addressed:**

- Important policy changes may not be communicated before implementation.

**Backend:** **None** — a notice has no effective date to be reminded about.

### US-2.12 — Reliable booking payment confirmation

**User story:** As a resident, I want amenity-booking payments to reliably reflect the correct paid
and confirmed status and ensure a booking is made, so that a successful payment always yields a
confirmed booking.

**Interviewee pain point addressed:**

- Amenity booking payments can fail even after money has been deducted.

**Backend:** **Served** — `POST /amenity-bookings/{bookingId}/pay` does both or neither. The gateway
is the simulator the product asked for, labelled as one on every row it writes.

---

## 3. Security manager

> No endpoint in this codebase is reachable by a security manager, because a staff member has no
> login (see [`USER_IDENTIFICATION.md`](USER_IDENTIFICATION.md)). The gate surface — registers,
> tankers, offline mode — has no tables either, and no owner. It is not in the admin-dashboard build
> order. Recorded here so the gap is a decision on the record rather than an oversight.
>
> **US-3.1 is the exception and is worth reading.** The baseline already models a scheduled,
> time-boxed, hashed access code. Nobody set out to build the story; the schema arrived at it anyway.

### US-3.1 — Event-specific access codes for functions

**User story:** As a security manager, I want residents to issue event-specific codes that admit
many guests over a configurable, pre-scheduled validity window, so that large functions are verified
without per-visitor approval and without weakening day-to-day security.

**Interviewee pain points addressed:**

- Current QR-code functionality is not suitable for large events involving hundreds of guests.
- Residents cannot conveniently generate event-based QR codes covering the full duration of
  functions.
- QR codes expire too quickly and cannot be scheduled several days in advance while activating only
  during the event.
- Security personnel must perform manual verification when residents cannot provide approvals during
  functions.

**Backend:** **Partial** — `visitor_requests.pass_hash` plus `valid_from` / `valid_until` is a
scheduled, time-boxed code, and `community_settings.visitor_code_ttl_minutes` already configures its
life. `POST /visitor-passes` issues one and `/cancel` revokes it, but **nothing verifies a code at
the gate**, which is the requirement the story is about, and nothing admits a second guest on one
code.

### US-3.2 — Auto guest access workflow on amenity booking

**User story:** As a security manager, I want a guest access setup triggered automatically when a
resident books a community hall or amenity, so that event entry is prepared without manual setup.

**Interviewee pain point addressed:**

- Security personnel must perform manual verification when residents cannot provide approvals during
  functions.

**Backend:** **None** — but the trigger point exists; see §14.

### US-3.3 — Digital registers

**User story:** As a security manager, I want to record inward and outward material movements,
including returnable and non-returnable materials, and other operational activities digitally, so
that I no longer need to keep manual registers.

**Interviewee pain point addressed:**

- Several operational activities require manual register maintenance.

**Backend:** **None.**

### US-3.4 — Digital water tanker log

**User story:** As a security manager, I want to log water tanker entries in the application, so
that tanker records are digital and auditable.

**Interviewee pain point addressed:**

- Water tanker management is not integrated into the application.

**Backend:** **None.**

### US-3.5 — Offline fallback verification

**User story:** As a security manager, I want a defined offline verification mode during outages, so
that gate operations continue with minimal disruption.

**Interviewee pain point addressed:**

- Network interruptions require temporary manual visitor verification.

**Backend:** **None.**

### US-3.6 — Long-term data retention and downloadable operational reports

**User story:** As a security manager, I want operational data retained long-term with downloadable
reports covering six months, one year, or longer, so that I can support audits and operational
reviews.

**Interviewee pain points addressed:**

- Historical records older than approximately three months are unavailable.
- Downloading and reviewing older operational reports is not supported.

**Backend:** **None** for gate operations. Retention itself is not a gap — nothing we write is ever
deleted or aged out.
