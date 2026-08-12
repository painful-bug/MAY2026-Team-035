# Complaint Engine v2 — Manual Testing Guide

**For:** anyone verifying the complaint workflows by hand, per user role.
**Prereqs:** the six `20260813*` migrations applied; backend + frontend running;
one community seeded with: 1 admin, 1 department (e.g. *Plumbing*) holding the
*Plumbing* skill, 1 department manager, 2 workers on its roster (call them
**W1**, **W2**) whose service-provider profiles hold the Plumbing skill, and
1 resident (**R**). Keep four browser sessions (or profiles) open — Admin,
Manager, Worker, Resident — and a fifth for W2 when a scenario needs both
workers.

Timers note: `manual_window` (2h/24h), offer timeout (30 min) and auto-close
(48h/72h) are `dispatch_tasks` rows. To test them without waiting, shrink the
row's `due_at` in SQL (`update dispatch_tasks set due_at = now() where …`) and
wait ≤15s for the dispatcher tick.

---

## 1. Resident (R)

### 1.1 Raise a complaint (skill parity check)

1. Resident portal → Complaints → **New complaint**.
2. Open the category dropdown. **Verify:** the entries are grouped trades and
   are *exactly* the list a service professional sees at onboarding
   (cross-check in a spare tab: worker portal → Register as provider — same
   groups, same names; both come from `GET /skills`).
3. File: title “Kitchen tap drips”, description, category *Plumbing*, priority
   **High**, department “Not sure”. Submit.
4. **Verify:** complaint appears with status *Pending*; the tracker shows
   **Raised** filled, the rest hollow.

### 1.2 Agree the visit time

5. Wait for the manager/supervisor to propose a slot (see §2.2). Notification
   arrives; complaint detail shows the proposed time with Accept / Decline.
6. Decline once. **Verify:** timeline shows “You declined the proposed time”;
   a new proposal arrives after the supervisor reschedules.
7. Accept the new time. **Verify:** tracker **Scheduled** node shows the slot.

### 1.3 Watch assignment + chat

8. After a worker accepts (§3.2): notification “⟨W1⟩ is coming”; tracker
   **Assigned** shows the name; the ChatDock (bubble, bottom corner) contains
   a thread for this job with a system line.
9. Send “What will this cost?” — negotiate. **Verify:** the worker's replies
   arrive; this is the only channel to the worker (the DM “to” list offers
   only the office).

### 1.4 Cancel and re-pool (disagreement path)

10. While the job is *Scheduled* (not started): complaint detail → **Cancel**.
    **Verify:** the dialog offers exactly two choices with plain-language
    consequences.
11. Choose **Send back for re-evaluation**. **Verify:** tracker annotation
    “Sent back for re-evaluation…”; chat thread is now locked (read-only,
    padlock); complaint still open.
12. Later (after §2.4 reassigns W2 and W2 starts the job): try to cancel.
    **Verify:** refused with “Work has begun — contact the office”.

### 1.5 Completion, rating, reopen

13. After the worker completes: notification asks you to **confirm or
    reopen**; status shows *Resolved*; tracker **Work done** filled.
14. Confirm with a 4-star rating. **Verify:** status *Resolved* (closed
    underneath), tracker complete.
15. Reopen from the detail (mandatory reason: “still drips”). **Verify:**
    tracker restarts with a *reopened* annotation; status back to *Pending*.
16. **Auto-close path:** on another resolved complaint, do nothing. Shrink the
    48h task → reminder notification. Shrink the 72h task → complaint closes
    unrated, notification says so; **Verify:** reopen still works afterwards.

---

## 2. Supervisor (department manager portal; repeat spot-checks as a worker with supervisor rank)

### 2.1 The queue

1. Raise a complaint as R (§1.1). **Verify:** manager notification on raise
   (new in v2 — supervisors/manager are pinged, not just admins); the
   complaint sits in Manager → Complaints under *Plumbing*.

### 2.2 Raise work + slot

2. Open it → raise a work order with a proposed visit slot. **Verify:**
   resident gets the accept/decline request (§1.2); after their decline,
   reschedule; after acceptance the job shows *scheduled* and the candidate
   picker becomes the next step.

### 2.3 The candidate picker

3. Open the job → **Offer job**. **Verify** the picker shows W1 and W2 with:
   open-job load, distance (if seeded), “another job that day” marker when
   applicable, and “away until ⟨date⟩” on a worker with a current time-off
   block. Give W2 an accepted job overlapping the slot (or a leave block over
   it) beforehand. **Verify:** W2 does not appear — occupied workers are
   invisible.
4. Offer to W1. **Verify:** job shows *offered · waiting on W1*; button copy
   said “offer”, not assign.

### 2.4 Declines, exclusion, override

5. Have W1 decline with a reason (§3.3). **Verify:** you are notified with
   the reason; reopening the picker, W1 is gone by default; the **Show
   excluded** toggle reveals W1 greyed with “declined earlier”.
6. Offer to W2 → W2 accepts. (For §1.4's re-pool: after R re-pools, the
   complaint appears in the queue's **Backlog — needs re-evaluation** section
   with a *returned* badge, and the cancelled-on worker is excluded.)

### 2.5 All-declined paths

7. **High priority:** fresh high complaint, both workers decline. **Verify:**
   the instant the second decline lands, the best-ranked (least-loaded) of
   the two is force-assigned; you are notified; the job shows accepted with a
   force marker in the detail.
8. **Medium priority:** repeat with a medium complaint. **Verify:** no forced
   assignment; you get “nobody accepted”; the job waits; you may re-offer,
   including to a decliner via the toggle (their offer is normal/declinable).

### 2.6 The fallback engine

9. Fresh complaint, resident accepts the slot, then do nothing. Shrink the
   `manual_window` task. **Verify:** offers appear to candidates without you;
   you are notified the system took over. Let the 30-min offer timer run (or
   shrink it): auto-assign lands on the best candidate.

### 2.7 Guards

10. Try raising a work order on a resolved/closed complaint. **Verify:**
    refused — “Reopen the complaint to raise more work.”
11. Try moving a complaint with a live job to another department (or accept a
    transfer request on one). **Verify:** refused — “Cancel or finish the
    open job first.”

---

## 3. Service worker (W1, W2)

### 3.1 Onboarding parity

1. Register as a provider (spare account). **Verify:** the trade list equals
   the resident dropdown (§1.1.2).

### 3.2 Offers and acceptance

2. As W1 with an offer pending (§2.3): Worker portal → Dashboard shows the
   offer with Accept / Decline. Accept. **Verify:** resident + supervisor
   notified; the job's chat thread exists in your ChatDock with the system
   line; the accept toast/deep link lands in it.

### 3.3 Decline

3. On a fresh offer, decline. **Verify:** a reason is mandatory; after it,
   the job leaves your list; you receive nothing further for this complaint
   unless the supervisor explicitly re-offers.

### 3.4 Forced assignment

4. Arrange §2.5.7 so you are the least-loaded decliner. **Verify:** the job
   returns as **assigned — critical**, with no decline control; the API
   refuses a decline attempt (409) if you try via a stale tab.

### 3.5 Doing the work

5. Reschedule the visit (your job detail → new time). **Verify:** resident's
   tracker updates the Scheduled node with an annotation; both sides
   notified.
6. Start the job. **Verify:** resident tracker → *In progress*; resident can
   no longer cancel (§1.4.12).
7. Complete it. **Verify:** resident tracker → *Work done*; the complaint
   turns *Resolved* by itself; the chat thread locks (read-only) — sending a
   message is refused.
8. **Failure path:** on another started job, report failure. **Verify:** a
   reason is mandatory; the complaint stays *In Progress*; after the 2h
   escalation task fires the manager is notified; the resident tracker shows
   *visit unsuccessful* and the line holds.

### 3.6 Availability

9. Worker portal → Availability: set a weekly window, add a time-off block
   ending next Friday (“back Friday”). **Verify:** during the block you
   receive no offers for overlapping slots; the supervisor's picker shows you
   “away until Friday” (greyed for overlapping slots, listed with the date
   otherwise).

---

## 4. Admin

1. **Triage:** raise a complaint under a skill no department holds.
   **Verify:** it lands in Admin → Complaint triage (unrouted); allot it to
   *Plumbing*; it appears in the manager's queue.
2. **Staff detail:** Admin → Complaints → open any complaint. **Verify:** the
   timeline shown is the real one (matches the resident's tracker/timeline,
   plus internal entries like the force-assign audit line and internal
   comments) — edit status/progress and confirm the timeline shows the real
   event afterwards, not a client-side imitation (reload to be sure).
3. **The retired dropdown:** Admin → Departments → a department's detail.
   **Verify:** the old “Assign to staff” dropdown is gone; in its place a
   “Raise work order” link lands on the work-order triage screen.
4. **Work-order triage as admin:** run §2.2–§2.6 from the admin mount of the
   same screens — every supervisor capability must work identically.
5. **Vocabulary lock (SQL):** `insert into complaint_events (complaint_id,
   event_type) values ('⟨id⟩','made_up_word');` **Verify:** refused by the
   CHECK constraint.

---

## 5. Cross-role regression sweep (15 minutes)

After any change to this engine, run the happy path end to end with all four
sessions side by side — raise → route → slot → consent → offer → accept →
chat → reschedule → start → complete → resolved → rate — confirming after
each step that **all four screens** (resident tracker, manager queue, worker
dashboard, admin detail) tell the same story, and that the notification bell
on each portal deep-links to a screen that opens. Then spot-check: one
decline, one re-pool, one auto-close, one reopen.
